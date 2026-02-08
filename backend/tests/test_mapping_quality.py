"""Tests for Mapping Quality service and API endpoints.

CTO-4: OMOP Mapping Quality - verifies coverage calculation, unmapped term
ranking, domain-specific coverage, confidence distribution, ambiguity rate,
empty dataset handling, and API endpoint responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.base import Domain
from app.schemas.mapping_quality import (
    ConfidenceBucket,
    DomainCoverage,
    MappingQualityReport,
    MappingTrendReport,
    MappingTrendPoint,
    SourceDistribution,
    UnmappedTerm,
)
from app.services.mapping_quality_service import (
    MappingQualityService,
    get_mapping_quality_service,
    reset_mapping_quality_service,
)


# ============================================================================
# Helpers: mock DB result rows
# ============================================================================


def _make_scalar_result(value):
    """Create a mock execute result that returns a scalar.

    SQLAlchemy Result.scalar() is synchronous, so we use MagicMock.
    """
    mock_result = MagicMock()
    mock_result.scalar.return_value = value
    return mock_result


def _make_all_result(rows):
    """Create a mock execute result whose .all() returns rows.

    SQLAlchemy Result.all() is synchronous, so we use MagicMock.
    """
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    return mock_result


def _row(**kwargs):
    """Create a SimpleNamespace to act as a DB row."""
    from types import SimpleNamespace
    return SimpleNamespace(**kwargs)


# ============================================================================
# Schema tests
# ============================================================================


class TestMappingQualitySchemas:
    """Test Pydantic schema construction and validation."""

    def test_confidence_bucket_creation(self):
        bucket = ConfidenceBucket(range_label="0.8-0.9", count=42, percentage=21.0)
        assert bucket.range_label == "0.8-0.9"
        assert bucket.count == 42
        assert bucket.percentage == 21.0

    def test_domain_coverage_creation(self):
        dc = DomainCoverage(
            domain="condition",
            total_mentions=100,
            mapped_mentions=85,
            coverage_pct=85.0,
            avg_confidence=0.92,
        )
        assert dc.domain == "condition"
        assert dc.coverage_pct == 85.0

    def test_unmapped_term_creation(self):
        term = UnmappedTerm(
            term_text="myocardial infarction",
            frequency=15,
            domain="condition",
            suggested_concepts=["MI", "Heart attack"],
        )
        assert term.term_text == "myocardial infarction"
        assert term.frequency == 15

    def test_unmapped_term_defaults(self):
        term = UnmappedTerm(term_text="xyz", frequency=1)
        assert term.domain is None
        assert term.suggested_concepts == []

    def test_mapping_quality_report_creation(self):
        report = MappingQualityReport(
            total_mentions=200,
            mapped_mentions=170,
            overall_coverage=85.0,
            ambiguity_rate=12.5,
            domain_coverage=[],
            confidence_distribution=[],
            source_distribution=[],
        )
        assert report.total_mentions == 200
        assert report.overall_coverage == 85.0
        assert report.ambiguity_rate == 12.5

    def test_source_distribution_creation(self):
        sd = SourceDistribution(source="exact", count=50, percentage=50.0)
        assert sd.source == "exact"

    def test_mapping_trend_point_creation(self):
        point = MappingTrendPoint(
            date="2026-01-15",
            coverage_pct=80.0,
            total_mentions=100,
            mapped_mentions=80,
            avg_confidence=0.85,
        )
        assert point.date == "2026-01-15"
        assert point.mapped_mentions == 80

    def test_mapping_trend_report_creation(self):
        report = MappingTrendReport(period_days=30, data_points=[])
        assert report.period_days == 30
        assert report.data_points == []


# ============================================================================
# Service unit tests (mock DB session)
# ============================================================================


class TestMappingQualityServiceCoverage:
    """Test coverage calculation with mock data."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_coverage_100_percent(self, service):
        """All mentions have at least one candidate -> 100% coverage."""
        session = AsyncMock()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # Call 1: total mentions
            if call_count == 1:
                return _make_scalar_result(10)
            # Call 2: mapped count (distinct mention_ids with candidates)
            if call_count == 2:
                return _make_scalar_result(10)
            # Call 3: ambiguity count
            if call_count == 3:
                return _make_scalar_result(0)
            # Call 4: total for domain coverage
            if call_count == 4:
                return _make_scalar_result(10)
            # Call 5: domain stats
            if call_count == 5:
                return _make_all_result([
                    _row(domain_id=Domain.CONDITION, mapped=10, avg_score=0.95),
                ])
            # Call 6: confidence scores
            if call_count == 6:
                return _make_all_result([(0.95,)] * 10)
            # Call 7: source distribution
            if call_count == 7:
                return _make_all_result([
                    _row(method="exact", cnt=10),
                ])
            return _make_scalar_result(0)

        session.execute = mock_execute

        report = await service.get_mapping_quality_report(session)
        assert report.overall_coverage == 100.0
        assert report.total_mentions == 10
        assert report.mapped_mentions == 10

    @pytest.mark.asyncio
    async def test_coverage_partial(self, service):
        """Half mentions mapped -> 50% coverage."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(100)
            if call_count == 2:
                return _make_scalar_result(50)
            if call_count == 3:
                return _make_scalar_result(10)
            if call_count == 4:
                return _make_scalar_result(100)
            if call_count == 5:
                return _make_all_result([
                    _row(domain_id=Domain.CONDITION, mapped=30, avg_score=0.85),
                    _row(domain_id=Domain.DRUG, mapped=20, avg_score=0.78),
                ])
            if call_count == 6:
                return _make_all_result([(0.85,)] * 50)
            if call_count == 7:
                return _make_all_result([
                    _row(method="exact", cnt=30),
                    _row(method="fuzzy", cnt=20),
                ])
            return _make_scalar_result(0)

        session.execute = mock_execute

        report = await service.get_mapping_quality_report(session)
        assert report.overall_coverage == 50.0
        assert report.total_mentions == 100
        assert report.mapped_mentions == 50

    @pytest.mark.asyncio
    async def test_coverage_zero_mentions(self, service):
        """No mentions at all -> 0% coverage, empty results."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(0)
            if call_count == 2:
                return _make_scalar_result(0)
            if call_count == 3:
                return _make_scalar_result(0)
            if call_count == 4:
                return _make_scalar_result(0)
            if call_count in (5, 6, 7):
                return _make_all_result([])
            return _make_scalar_result(0)

        session.execute = mock_execute

        report = await service.get_mapping_quality_report(session)
        assert report.overall_coverage == 0.0
        assert report.total_mentions == 0
        assert report.mapped_mentions == 0
        assert report.ambiguity_rate == 0.0
        assert report.domain_coverage == []


class TestMappingQualityServiceAmbiguity:
    """Test ambiguity rate calculation."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_ambiguity_rate_calculation(self, service):
        """20 of 100 mentions have >1 candidate -> 20% ambiguity."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(100)
            if call_count == 2:
                return _make_scalar_result(80)
            if call_count == 3:
                return _make_scalar_result(20)  # 20 ambiguous
            if call_count == 4:
                return _make_scalar_result(100)
            if call_count == 5:
                return _make_all_result([])
            if call_count == 6:
                return _make_all_result([])
            if call_count == 7:
                return _make_all_result([])
            return _make_scalar_result(0)

        session.execute = mock_execute

        report = await service.get_mapping_quality_report(session)
        assert report.ambiguity_rate == 20.0

    @pytest.mark.asyncio
    async def test_ambiguity_rate_zero(self, service):
        """No ambiguous mentions -> 0% ambiguity."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(50)
            if call_count == 2:
                return _make_scalar_result(50)
            if call_count == 3:
                return _make_scalar_result(0)  # no ambiguity
            if call_count == 4:
                return _make_scalar_result(50)
            if call_count == 5:
                return _make_all_result([])
            if call_count == 6:
                return _make_all_result([])
            if call_count == 7:
                return _make_all_result([])
            return _make_scalar_result(0)

        session.execute = mock_execute

        report = await service.get_mapping_quality_report(session)
        assert report.ambiguity_rate == 0.0


class TestMappingQualityServiceUnmapped:
    """Test unmapped term retrieval."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_unmapped_terms_ranking(self, service):
        """Unmapped terms should be sorted by frequency descending."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([
            _row(term="unknown term a", freq=25),
            _row(term="unknown term b", freq=10),
            _row(term="unknown term c", freq=5),
        ]))

        terms = await service.get_unmapped_terms(session, limit=10)
        assert len(terms) == 3
        assert terms[0].term_text == "unknown term a"
        assert terms[0].frequency == 25
        assert terms[1].frequency == 10
        assert terms[2].frequency == 5

    @pytest.mark.asyncio
    async def test_unmapped_terms_empty(self, service):
        """No unmapped terms -> empty list."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([]))

        terms = await service.get_unmapped_terms(session)
        assert terms == []

    @pytest.mark.asyncio
    async def test_unmapped_terms_with_limit(self, service):
        """Limit parameter should be respected."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([
            _row(term="term1", freq=50),
            _row(term="term2", freq=40),
        ]))

        terms = await service.get_unmapped_terms(session, limit=2)
        assert len(terms) == 2

    @pytest.mark.asyncio
    async def test_unmapped_terms_with_domain_filter(self, service):
        """Domain filter passes through to result."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([
            _row(term="unknown drug", freq=12),
        ]))

        terms = await service.get_unmapped_terms(session, domain="drug")
        assert len(terms) == 1
        assert terms[0].domain == "drug"


class TestMappingQualityServiceDomainCoverage:
    """Test per-domain coverage breakdown."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_domain_coverage_multiple_domains(self, service):
        """Multiple domains should each get their own coverage entry."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(200)
            if call_count == 2:
                return _make_all_result([
                    _row(domain_id=Domain.CONDITION, mapped=80, avg_score=0.90),
                    _row(domain_id=Domain.DRUG, mapped=50, avg_score=0.85),
                    _row(domain_id=Domain.MEASUREMENT, mapped=30, avg_score=0.75),
                ])
            return _make_scalar_result(0)

        session.execute = mock_execute

        coverages = await service.get_mapping_coverage_by_domain(session)
        assert len(coverages) == 3
        # Sorted by coverage descending
        assert coverages[0].domain == "condition"
        assert coverages[0].mapped_mentions == 80
        assert coverages[1].domain == "drug"
        assert coverages[2].domain == "measurement"

    @pytest.mark.asyncio
    async def test_domain_coverage_empty(self, service):
        """No mentions -> empty domain coverage list."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_result(0)
            return _make_all_result([])

        session.execute = mock_execute

        coverages = await service.get_mapping_coverage_by_domain(session)
        assert coverages == []


class TestMappingQualityServiceConfidenceDistribution:
    """Test confidence distribution histogram."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_confidence_buckets_with_data(self, service):
        """Scores should be distributed into 10 buckets."""
        session = AsyncMock()
        # Scores: 5 at 0.95, 3 at 0.75, 2 at 0.5
        scores = [(0.95,)] * 5 + [(0.75,)] * 3 + [(0.5,)] * 2
        session.execute = AsyncMock(return_value=_make_all_result(scores))

        buckets = await service._get_confidence_distribution(session)
        assert len(buckets) == 10

        # Check the 0.9-1.0 bucket has 5
        high_bucket = [b for b in buckets if b.range_label == "0.9-1.0"][0]
        assert high_bucket.count == 5
        assert high_bucket.percentage == 50.0

        # Check the 0.7-0.8 bucket has 3
        mid_bucket = [b for b in buckets if b.range_label == "0.7-0.8"][0]
        assert mid_bucket.count == 3

    @pytest.mark.asyncio
    async def test_confidence_buckets_empty(self, service):
        """No scores -> all buckets have count 0."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([]))

        buckets = await service._get_confidence_distribution(session)
        assert len(buckets) == 10
        assert all(b.count == 0 for b in buckets)
        assert all(b.percentage == 0.0 for b in buckets)


class TestMappingQualityServiceSourceDistribution:
    """Test mapping source distribution."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_source_distribution(self, service):
        """Multiple sources should appear with correct percentages."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([
            _row(method="exact", cnt=60),
            _row(method="fuzzy", cnt=30),
            _row(method="ml", cnt=10),
        ]))

        dist = await service._get_source_distribution(session)
        assert len(dist) == 3
        assert dist[0].source == "exact"
        assert dist[0].percentage == 60.0
        assert dist[1].source == "fuzzy"
        assert dist[1].percentage == 30.0

    @pytest.mark.asyncio
    async def test_source_distribution_empty(self, service):
        """No candidates -> empty source distribution."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([]))

        dist = await service._get_source_distribution(session)
        assert dist == []


class TestMappingQualityServiceTrends:
    """Test mapping trends over time."""

    @pytest.fixture
    def service(self):
        return MappingQualityService()

    @pytest.mark.asyncio
    async def test_trends_with_data(self, service):
        """Trend report should have daily data points."""
        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Daily mention counts
                return _make_all_result([
                    _row(day="2026-01-10", total=50),
                    _row(day="2026-01-11", total=60),
                ])
            if call_count == 2:
                # Daily mapped counts
                return _make_all_result([
                    _row(day="2026-01-10", mapped=40, avg_conf=0.88),
                    _row(day="2026-01-11", mapped=55, avg_conf=0.91),
                ])
            return _make_all_result([])

        session.execute = mock_execute

        report = await service.get_mapping_trends(session, days=30)
        assert report.period_days == 30
        assert len(report.data_points) == 2
        assert report.data_points[0].date == "2026-01-10"
        assert report.data_points[0].total_mentions == 50
        assert report.data_points[0].mapped_mentions == 40
        assert report.data_points[0].coverage_pct == 80.0

    @pytest.mark.asyncio
    async def test_trends_empty(self, service):
        """No data in period -> empty data points."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([]))

        report = await service.get_mapping_trends(session, days=7)
        assert report.period_days == 7
        assert report.data_points == []


# ============================================================================
# Singleton tests
# ============================================================================


class TestMappingQualityServiceSingleton:
    """Test service singleton management."""

    def test_get_returns_same_instance(self):
        reset_mapping_quality_service()
        svc1 = get_mapping_quality_service()
        svc2 = get_mapping_quality_service()
        assert svc1 is svc2

    def test_reset_clears_singleton(self):
        svc1 = get_mapping_quality_service()
        reset_mapping_quality_service()
        svc2 = get_mapping_quality_service()
        assert svc1 is not svc2


# ============================================================================
# API endpoint tests
# ============================================================================


class TestMappingQualityAPI:
    """Test API endpoint responses."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_mapping_quality_report_endpoint(self, client):
        """GET /api/v1/data-quality/mapping returns 200 with report shape."""
        mock_report = MappingQualityReport(
            total_mentions=100,
            mapped_mentions=80,
            overall_coverage=80.0,
            ambiguity_rate=15.0,
            domain_coverage=[],
            confidence_distribution=[],
            source_distribution=[],
        )

        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_mapping_quality_report.return_value = mock_report
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping")

        assert response.status_code == 200
        data = response.json()
        assert data["total_mentions"] == 100
        assert data["mapped_mentions"] == 80
        assert data["overall_coverage"] == 80.0
        assert data["ambiguity_rate"] == 15.0

    @pytest.mark.asyncio
    async def test_get_unmapped_terms_endpoint(self, client):
        """GET /api/v1/data-quality/mapping/unmapped returns list."""
        mock_terms = [
            UnmappedTerm(term_text="foo", frequency=10),
            UnmappedTerm(term_text="bar", frequency=5),
        ]

        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_unmapped_terms.return_value = mock_terms
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping/unmapped")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["term_text"] == "foo"
        assert data[0]["frequency"] == 10

    @pytest.mark.asyncio
    async def test_get_domain_coverage_endpoint(self, client):
        """GET /api/v1/data-quality/mapping/coverage returns domain list."""
        mock_coverage = [
            DomainCoverage(
                domain="condition",
                total_mentions=100,
                mapped_mentions=90,
                coverage_pct=90.0,
                avg_confidence=0.92,
            ),
        ]

        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_mapping_coverage_by_domain.return_value = mock_coverage
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping/coverage")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["domain"] == "condition"
        assert data[0]["coverage_pct"] == 90.0

    @pytest.mark.asyncio
    async def test_get_trends_endpoint(self, client):
        """GET /api/v1/data-quality/mapping/trends returns trend data."""
        mock_trends = MappingTrendReport(
            period_days=30,
            data_points=[
                MappingTrendPoint(
                    date="2026-01-15",
                    coverage_pct=85.0,
                    total_mentions=200,
                    mapped_mentions=170,
                    avg_confidence=0.88,
                ),
            ],
        )

        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_mapping_trends.return_value = mock_trends
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping/trends?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30
        assert len(data["data_points"]) == 1
        assert data["data_points"][0]["coverage_pct"] == 85.0

    @pytest.mark.asyncio
    async def test_unmapped_terms_limit_param(self, client):
        """GET /api/v1/data-quality/mapping/unmapped?limit=5 passes limit."""
        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_unmapped_terms.return_value = []
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping/unmapped?limit=5")

        assert response.status_code == 200
        mock_svc.get_unmapped_terms.assert_called_once()
        call_kwargs = mock_svc.get_unmapped_terms.call_args
        assert call_kwargs.kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_quality_report_with_domain_filter(self, client):
        """GET /api/v1/data-quality/mapping?domain=drug passes filter."""
        mock_report = MappingQualityReport(
            total_mentions=50,
            mapped_mentions=40,
            overall_coverage=80.0,
            ambiguity_rate=10.0,
        )

        with patch(
            "app.api.mapping_quality.get_mapping_quality_service"
        ) as mock_get_svc:
            mock_svc = AsyncMock()
            mock_svc.get_mapping_quality_report.return_value = mock_report
            mock_get_svc.return_value = mock_svc

            async with client as ac:
                response = await ac.get("/api/v1/data-quality/mapping?domain=drug")

        assert response.status_code == 200
        mock_svc.get_mapping_quality_report.assert_called_once()
        call_kwargs = mock_svc.get_mapping_quality_report.call_args
        assert call_kwargs.kwargs["domain_filter"] == "drug"
