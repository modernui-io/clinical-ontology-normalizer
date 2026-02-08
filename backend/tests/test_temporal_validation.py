"""Tests for CMO-1.3: Temporal Reasoning Validation.

Comprehensive test suite for temporal eligibility filtering in clinical
trial patient screening.  Covers:

- "Within last N days" filtering (facts inside and outside window)
- "Active diagnosis" filtering (no end date = active)
- Date range filtering (BETWEEN direction)
- Missing date handling (UNKNOWN policy, INCLUDE, EXCLUDE)
- Relative date calculation accuracy
- Integration with trial eligibility screening
- Temporal exclusion criteria (e.g., no cancer in 5 years)
- Edge cases: future dates, same-day, midnight boundary
- Realistic trial criteria (EYLEA HD, Dupixent, Libtayo)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import NodeType
from app.schemas.temporal import (
    MissingDatePolicy,
    TemporalCriterion,
    TemporalDirection,
    TemporalFilterConfig,
    TemporalReferencePoint,
    TemporalResult,
    TemporalStatus,
)
from app.services.temporal_eligibility_service import TemporalEligibilityService
from app.services.trial_eligibility_service import TrialEligibilityService


# =============================================================================
# Async Engine / Session Fixtures
# =============================================================================


@pytest.fixture(scope="function")
async def engine():
    """Create an async SQLite in-memory engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    tables = [
        ClinicalFact.__table__,
        KGNode.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=tables)
    await eng.dispose()


@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create an async database session for testing."""
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as sess:
        yield sess
        await sess.rollback()


# =============================================================================
# Service Fixtures
# =============================================================================


@pytest.fixture
def temporal_service() -> TemporalEligibilityService:
    """Create a fresh TemporalEligibilityService."""
    return TemporalEligibilityService()


@pytest.fixture
def trial_service() -> TrialEligibilityService:
    """Create a fresh TrialEligibilityService (skip DB loading)."""
    svc = TrialEligibilityService()
    svc._loaded_from_db = True
    return svc


# =============================================================================
# Helper: Fake fact objects for unit testing (no DB needed)
# =============================================================================


class FakeFact:
    """Lightweight stand-in for ClinicalFact with id, start_date, end_date."""

    def __init__(
        self,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        fact_id: str | None = None,
    ):
        self.id = fact_id or str(uuid4())
        self.start_date = start_date
        self.end_date = end_date


# =============================================================================
# Helper: insert clinical facts into the test DB
# =============================================================================


async def _insert_fact(
    session: AsyncSession,
    *,
    patient_id: str,
    domain: Domain,
    concept_name: str,
    assertion: Assertion = Assertion.PRESENT,
    confidence: float = 0.95,
    value: str | None = None,
    unit: str | None = None,
    omop_concept_id: int = 0,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ClinicalFact:
    """Insert a ClinicalFact and return it."""
    fact = ClinicalFact(
        id=str(uuid4()),
        patient_id=patient_id,
        domain=domain,
        omop_concept_id=omop_concept_id,
        concept_name=concept_name,
        assertion=assertion,
        temporality=Temporality.CURRENT,
        experiencer=Experiencer.PATIENT,
        confidence=confidence,
        value=value,
        unit=unit,
        start_date=start_date,
        end_date=end_date,
    )
    session.add(fact)
    await session.flush()
    return fact


async def _insert_patient_node(
    session: AsyncSession,
    *,
    patient_id: str,
    birth_date: str | None = None,
    gender: str | None = None,
) -> KGNode:
    """Insert a KGNode PATIENT."""
    props: dict = {}
    if birth_date:
        props["birth_date"] = birth_date
    if gender:
        props["gender"] = gender
    node = KGNode(
        id=str(uuid4()),
        patient_id=patient_id,
        node_type=NodeType.PATIENT,
        label=f"Patient {patient_id}",
        properties=props,
    )
    session.add(node)
    await session.flush()
    return node


# =============================================================================
# Reference dates
# =============================================================================

NOW = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# 1. WITHIN_LAST filtering tests
# =============================================================================


class TestWithinLastFiltering:
    """Tests for 'within last N days' temporal filtering."""

    def test_fact_inside_window(self, temporal_service):
        """A fact recorded 30 days ago should match a 90-day window."""
        fact = FakeFact(start_date=NOW - timedelta(days=30))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids
        assert len(result.excluded_fact_ids) == 0

    def test_fact_outside_window(self, temporal_service):
        """A fact recorded 120 days ago should NOT match a 90-day window."""
        fact = FakeFact(start_date=NOW - timedelta(days=120))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET
        assert fact.id in result.excluded_fact_ids
        assert len(result.matched_fact_ids) == 0

    def test_fact_exactly_on_boundary(self, temporal_service):
        """A fact exactly at the boundary (90 days ago) should match."""
        fact = FakeFact(start_date=NOW - timedelta(days=90))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids

    def test_mixed_facts_inside_and_outside(self, temporal_service):
        """Only facts within the window should be in matched_fact_ids."""
        recent = FakeFact(start_date=NOW - timedelta(days=10))
        old = FakeFact(start_date=NOW - timedelta(days=200))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [recent, old], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert recent.id in result.matched_fact_ids
        assert old.id in result.excluded_fact_ids

    def test_fact_today(self, temporal_service):
        """A fact recorded today should always match any WITHIN_LAST window."""
        fact = FakeFact(start_date=NOW)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET

    def test_zero_day_window(self, temporal_service):
        """A 0-day window should only match facts at exactly the reference time."""
        same_time = FakeFact(start_date=NOW)
        yesterday = FakeFact(start_date=NOW - timedelta(days=1))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=0,
        )
        result = temporal_service.apply_temporal_filter(
            [same_time, yesterday], criterion, reference_date=NOW,
        )
        assert same_time.id in result.matched_fact_ids
        assert yesterday.id in result.excluded_fact_ids

    def test_large_window_5_years(self, temporal_service):
        """A 5-year window (1825 days) should include facts from 4 years ago."""
        four_years_ago = FakeFact(start_date=NOW - timedelta(days=365 * 4))
        six_years_ago = FakeFact(start_date=NOW - timedelta(days=365 * 6))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1825,
        )
        result = temporal_service.apply_temporal_filter(
            [four_years_ago, six_years_ago], criterion, reference_date=NOW,
        )
        assert four_years_ago.id in result.matched_fact_ids
        assert six_years_ago.id in result.excluded_fact_ids


# =============================================================================
# 2. ACTIVE diagnosis tests
# =============================================================================


class TestActiveDiagnosis:
    """Tests for 'active diagnosis' filtering (no end date or end > now)."""

    def test_no_end_date_is_active(self, temporal_service):
        """A condition with no end_date is considered active."""
        fact = FakeFact(start_date=NOW - timedelta(days=365), end_date=None)
        criterion = TemporalCriterion(direction=TemporalDirection.ACTIVE)
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids

    def test_end_date_in_future_is_active(self, temporal_service):
        """A condition with end_date in the future is active."""
        fact = FakeFact(
            start_date=NOW - timedelta(days=100),
            end_date=NOW + timedelta(days=30),
        )
        criterion = TemporalCriterion(direction=TemporalDirection.ACTIVE)
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET

    def test_end_date_in_past_is_resolved(self, temporal_service):
        """A condition with end_date in the past is resolved (inactive)."""
        fact = FakeFact(
            start_date=NOW - timedelta(days=365),
            end_date=NOW - timedelta(days=30),
        )
        criterion = TemporalCriterion(direction=TemporalDirection.ACTIVE)
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET
        assert fact.id in result.excluded_fact_ids

    def test_active_with_min_duration(self, temporal_service):
        """Active diagnosis with min_duration_days requirement."""
        # Diagnosed 400 days ago, no end date -> active for 400 days
        long_term = FakeFact(start_date=NOW - timedelta(days=400))
        # Diagnosed 30 days ago -> active but only 30 days
        recent = FakeFact(start_date=NOW - timedelta(days=30))
        criterion = TemporalCriterion(
            direction=TemporalDirection.ACTIVE,
            min_duration_days=365,
        )
        result = temporal_service.apply_temporal_filter(
            [long_term, recent], criterion, reference_date=NOW,
        )
        assert long_term.id in result.matched_fact_ids
        assert recent.id in result.excluded_fact_ids

    def test_active_no_start_date(self, temporal_service):
        """Active check with no start_date -- still active if no end_date."""
        fact = FakeFact(start_date=None, end_date=None)
        criterion = TemporalCriterion(direction=TemporalDirection.ACTIVE)
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        # No end date means active, even without start date
        assert result.status == TemporalStatus.MET


# =============================================================================
# 3. Date range (BETWEEN) tests
# =============================================================================


class TestDateRangeFiltering:
    """Tests for date range (BETWEEN) filtering."""

    def test_fact_within_range(self, temporal_service):
        """A fact within [start, end] range should match."""
        range_start = datetime(2025, 6, 1, tzinfo=timezone.utc)
        range_end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        fact = FakeFact(start_date=datetime(2025, 9, 15, tzinfo=timezone.utc))
        criterion = TemporalCriterion(
            direction=TemporalDirection.BETWEEN,
            start_date=range_start,
            end_date=range_end,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids

    def test_fact_before_range(self, temporal_service):
        """A fact before the range should not match."""
        range_start = datetime(2025, 6, 1, tzinfo=timezone.utc)
        range_end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        fact = FakeFact(start_date=datetime(2025, 1, 15, tzinfo=timezone.utc))
        criterion = TemporalCriterion(
            direction=TemporalDirection.BETWEEN,
            start_date=range_start,
            end_date=range_end,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET
        assert fact.id in result.excluded_fact_ids

    def test_fact_after_range(self, temporal_service):
        """A fact after the range should not match."""
        range_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        range_end = datetime(2025, 6, 30, tzinfo=timezone.utc)
        fact = FakeFact(start_date=datetime(2025, 9, 15, tzinfo=timezone.utc))
        criterion = TemporalCriterion(
            direction=TemporalDirection.BETWEEN,
            start_date=range_start,
            end_date=range_end,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET

    def test_fact_on_range_boundary(self, temporal_service):
        """A fact exactly on the boundary should match."""
        boundary = datetime(2025, 6, 1, tzinfo=timezone.utc)
        fact = FakeFact(start_date=boundary)
        criterion = TemporalCriterion(
            direction=TemporalDirection.BETWEEN,
            start_date=boundary,
            end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET


# =============================================================================
# 4. Missing date handling tests
# =============================================================================


class TestMissingDateHandling:
    """Tests for handling facts without date information."""

    def test_missing_date_unknown_policy(self, temporal_service):
        """With UNKNOWN policy, undated facts should result in UNKNOWN status."""
        fact = FakeFact(start_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.UNKNOWN,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.UNKNOWN
        assert fact.id in result.undated_fact_ids

    def test_missing_date_include_policy(self, temporal_service):
        """With INCLUDE policy, undated facts should be treated as matched."""
        fact = FakeFact(start_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.INCLUDE,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids

    def test_missing_date_exclude_policy(self, temporal_service):
        """With EXCLUDE policy, undated facts should be excluded."""
        fact = FakeFact(start_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.EXCLUDE,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET
        assert fact.id in result.excluded_fact_ids

    def test_mixed_dated_and_undated_unknown_policy(self, temporal_service):
        """With UNKNOWN policy, dated+undated facts: dated take priority."""
        dated = FakeFact(start_date=NOW - timedelta(days=10))
        undated = FakeFact(start_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.UNKNOWN,
        )
        result = temporal_service.apply_temporal_filter(
            [dated, undated], criterion, reference_date=NOW,
        )
        # MET because the dated fact matches
        assert result.status == TemporalStatus.MET
        assert dated.id in result.matched_fact_ids
        assert undated.id in result.undated_fact_ids

    def test_all_undated_with_exclude(self, temporal_service):
        """All undated facts with EXCLUDE policy -> NOT_MET."""
        facts = [FakeFact(start_date=None) for _ in range(3)]
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.EXCLUDE,
        )
        result = temporal_service.apply_temporal_filter(
            facts, criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET


# =============================================================================
# 5. Relative date calculation accuracy
# =============================================================================


class TestRelativeDateCalculation:
    """Tests for accurate relative date computations."""

    def test_90_day_lookback(self, temporal_service):
        """Verify 90-day lookback window is computed correctly."""
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        window_start, window_end = temporal_service._compute_window(criterion, NOW)
        expected_start = NOW - timedelta(days=90)
        assert window_start == expected_start
        assert window_end == NOW

    def test_365_day_lookback(self, temporal_service):
        """Verify 1-year lookback."""
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=365,
        )
        window_start, window_end = temporal_service._compute_window(criterion, NOW)
        expected_start = NOW - timedelta(days=365)
        assert window_start == expected_start

    def test_1825_day_lookback_5_years(self, temporal_service):
        """Verify 5-year lookback (1825 days)."""
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1825,
        )
        window_start, window_end = temporal_service._compute_window(criterion, NOW)
        expected_start = NOW - timedelta(days=1825)
        assert window_start == expected_start

    def test_default_lookback_from_config(self):
        """When no time_window_days specified, use config default."""
        config = TemporalFilterConfig(default_lookback_days=180)
        svc = TemporalEligibilityService(config=config)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
        )
        window_start, window_end = svc._compute_window(criterion, NOW)
        expected_start = NOW - timedelta(days=180)
        assert window_start == expected_start

    def test_active_window_is_none(self, temporal_service):
        """ACTIVE direction should have None window bounds."""
        criterion = TemporalCriterion(direction=TemporalDirection.ACTIVE)
        window_start, window_end = temporal_service._compute_window(criterion, NOW)
        assert window_start is None
        assert window_end is None


# =============================================================================
# 6. Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for temporal filtering."""

    def test_future_fact_date(self, temporal_service):
        """A fact with a future date within a WITHIN_LAST window should match."""
        future_fact = FakeFact(start_date=NOW + timedelta(hours=6))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1,
        )
        result = temporal_service.apply_temporal_filter(
            [future_fact], criterion, reference_date=NOW,
        )
        # Future dates are within [NOW-1day, NOW], so this is outside
        assert future_fact.id in result.excluded_fact_ids

    def test_same_day_fact(self, temporal_service):
        """A fact on the same day as reference should match."""
        same_day = FakeFact(start_date=NOW.replace(hour=0, minute=0, second=0))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1,
        )
        result = temporal_service.apply_temporal_filter(
            [same_day], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET

    def test_midnight_boundary(self, temporal_service):
        """Test fact exactly at midnight boundary of the window."""
        midnight = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
        exactly_at_boundary = midnight - timedelta(days=90)
        fact = FakeFact(start_date=exactly_at_boundary)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=midnight,
        )
        assert fact.id in result.matched_fact_ids

    def test_empty_facts_list(self, temporal_service):
        """Empty facts list should return INSUFFICIENT_DATA."""
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.INSUFFICIENT_DATA
        assert result.total_facts_evaluated == 0

    def test_naive_datetime_handling(self, temporal_service):
        """Facts with naive datetimes should be treated as UTC."""
        naive_dt = datetime(2026, 2, 1, 12, 0, 0)  # No tzinfo
        fact = FakeFact(start_date=naive_dt)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=30,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert fact.id in result.matched_fact_ids

    def test_result_evidence_text(self, temporal_service):
        """Evidence text should describe the temporal filter applied."""
        fact = FakeFact(start_date=NOW - timedelta(days=10))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert "within last 90 days" in result.evidence
        assert "1/1 facts within window" in result.evidence


# =============================================================================
# 7. Temporal exclusion criteria
# =============================================================================


class TestTemporalExclusion:
    """Tests for temporal exclusion criteria (e.g., no cancer in 5 years)."""

    def test_cancer_within_5_years_excluded(self, temporal_service):
        """Cancer diagnosis within 5 years should match (for exclusion use)."""
        cancer_3yr = FakeFact(start_date=NOW - timedelta(days=365 * 3))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1825,  # 5 years
        )
        result = temporal_service.apply_temporal_filter(
            [cancer_3yr], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        # This means the patient HAS cancer in window -> would be excluded

    def test_cancer_outside_5_years_not_excluded(self, temporal_service):
        """Cancer diagnosis >5 years ago should NOT match the window."""
        cancer_7yr = FakeFact(start_date=NOW - timedelta(days=365 * 7))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=1825,  # 5 years
        )
        result = temporal_service.apply_temporal_filter(
            [cancer_7yr], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET
        # Patient had cancer but it's outside the exclusion window

    def test_prior_treatment_within_12_months(self, temporal_service):
        """Prior anti-PD-1 therapy within 12 months should match."""
        treatment_6mo = FakeFact(start_date=NOW - timedelta(days=180))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=365,  # 12 months
        )
        result = temporal_service.apply_temporal_filter(
            [treatment_6mo], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET

    def test_prior_treatment_outside_12_months(self, temporal_service):
        """Prior anti-PD-1 therapy >12 months ago should NOT match."""
        treatment_18mo = FakeFact(start_date=NOW - timedelta(days=540))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=365,
        )
        result = temporal_service.apply_temporal_filter(
            [treatment_18mo], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET


# =============================================================================
# 8. Duration-based criteria
# =============================================================================


class TestDurationCriteria:
    """Tests for minimum duration requirements."""

    def test_diagnosis_for_over_1_year(self, temporal_service):
        """Diagnosis present for >= 365 days should meet criterion."""
        fact = FakeFact(start_date=NOW - timedelta(days=400))
        criterion = TemporalCriterion(
            direction=TemporalDirection.ACTIVE,
            min_duration_days=365,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET

    def test_diagnosis_under_1_year(self, temporal_service):
        """Diagnosis present for < 365 days should NOT meet criterion."""
        fact = FakeFact(start_date=NOW - timedelta(days=200))
        criterion = TemporalCriterion(
            direction=TemporalDirection.ACTIVE,
            min_duration_days=365,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.NOT_MET

    def test_duration_with_missing_start_date(self, temporal_service):
        """Duration check without start_date: condition still active (no end)."""
        fact = FakeFact(start_date=None, end_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.ACTIVE,
            min_duration_days=365,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        # Active but can't verify duration -- still considered matched
        # because no end_date means active
        assert result.status == TemporalStatus.MET


# =============================================================================
# 9. TemporalFilterConfig tests
# =============================================================================


class TestTemporalFilterConfig:
    """Tests for TemporalFilterConfig behavior."""

    def test_require_dates_forces_undated(self):
        """When require_dates=True, undated facts go to undated bucket."""
        config = TemporalFilterConfig(require_dates=True)
        svc = TemporalEligibilityService(config=config)
        fact = FakeFact(start_date=None)
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
            missing_date_policy=MissingDatePolicy.INCLUDE,
        )
        result = svc.apply_temporal_filter([fact], criterion, reference_date=NOW)
        # require_dates overrides the criterion-level INCLUDE policy
        assert fact.id in result.undated_fact_ids

    def test_default_lookback(self):
        """Default lookback is used when criterion has no time_window_days."""
        config = TemporalFilterConfig(default_lookback_days=60)
        svc = TemporalEligibilityService(config=config)
        within_60 = FakeFact(start_date=NOW - timedelta(days=50))
        outside_60 = FakeFact(start_date=NOW - timedelta(days=80))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            # No time_window_days -> use config default
        )
        result = svc.apply_temporal_filter(
            [within_60, outside_60], criterion, reference_date=NOW,
        )
        assert within_60.id in result.matched_fact_ids
        assert outside_60.id in result.excluded_fact_ids


# =============================================================================
# 10. Database integration: evaluate_temporal_criterion
# =============================================================================


class TestEvaluateTemporalCriterion:
    """Tests for evaluate_temporal_criterion (uses async DB)."""

    @pytest.mark.asyncio
    async def test_query_filters_by_domain_and_term(self, session, temporal_service):
        """evaluate_temporal_criterion should query the right facts."""
        patient_id = "TEMP-DB-001"
        recent_hba1c = await _insert_fact(
            session,
            patient_id=patient_id,
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="7.2",
            unit="%",
            start_date=NOW - timedelta(days=30),
        )
        old_hba1c = await _insert_fact(
            session,
            patient_id=patient_id,
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="8.5",
            unit="%",
            start_date=NOW - timedelta(days=200),
        )
        await session.commit()

        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = await temporal_service.evaluate_temporal_criterion(
            patient_id=patient_id,
            criterion=criterion,
            session=session,
            domain=Domain.MEASUREMENT,
            concept_terms=["Hemoglobin A1c"],
            reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert str(recent_hba1c.id) in result.matched_fact_ids
        assert str(old_hba1c.id) in result.excluded_fact_ids

    @pytest.mark.asyncio
    async def test_no_matching_facts(self, session, temporal_service):
        """No matching facts -> INSUFFICIENT_DATA."""
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = await temporal_service.evaluate_temporal_criterion(
            patient_id="NONEXISTENT",
            criterion=criterion,
            session=session,
            domain=Domain.MEASUREMENT,
            concept_terms=["Hemoglobin A1c"],
            reference_date=NOW,
        )
        assert result.status == TemporalStatus.INSUFFICIENT_DATA


# =============================================================================
# 11. Integration with TrialEligibilityService
# =============================================================================


class TestTrialEligibilityIntegration:
    """Tests verifying temporal filtering is wired into trial screening."""

    @pytest.mark.asyncio
    async def test_criterion_with_temporal_window_filters_old_facts(
        self, session, trial_service,
    ):
        """A criterion with temporal_window_days should exclude old facts."""
        patient_id = "TEMP-INTEG-001"
        await _insert_patient_node(
            session, patient_id=patient_id, birth_date="1980-01-01", gender="M",
        )

        # HbA1c from 200 days ago (outside 90-day window)
        await _insert_fact(
            session,
            patient_id=patient_id,
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="7.2",
            unit="%",
            start_date=NOW - timedelta(days=200),
        )
        await session.commit()

        # Create trial with temporal constraint on HbA1c
        from app.schemas.trial import TrialCreate
        from app.models.trial import TrialPhase, TrialStatus

        trial = trial_service.create_trial(TrialCreate(
            name="Temporal Test Trial",
            sponsor="Test",
            phase=TrialPhase.PHASE_3,
            status=TrialStatus.RECRUITING,
            inclusion_criteria={
                "criteria": [
                    {
                        "criterion_type": "measurement",
                        "name": "Recent HbA1c",
                        "codes": [
                            {"code": "4548-4", "display": "Hemoglobin A1c"},
                        ],
                        "code_system": "LOINC",
                        "temporal_window_days": 90,
                    },
                ],
                "root_operator": "AND",
            },
            exclusion_criteria={"criteria": [], "root_operator": "AND"},
            enrollment_target=100,
        ))

        eligibility = await trial_service.check_patient_eligibility(
            str(trial.id), patient_id, session=session,
        )
        assert eligibility is not None
        # The HbA1c is 200 days old, outside the 90-day window -> NOT_MET
        assert eligibility.eligible is False
        hba1c_detail = next(
            (cr for cr in eligibility.criteria_details if cr.criterion_name == "Recent HbA1c"),
            None,
        )
        assert hba1c_detail is not None
        assert hba1c_detail.status == "NOT_MET"

    @pytest.mark.asyncio
    async def test_criterion_with_temporal_window_includes_recent_facts(
        self, session, trial_service,
    ):
        """A criterion with temporal_window_days should include recent facts."""
        patient_id = "TEMP-INTEG-002"
        await _insert_patient_node(
            session, patient_id=patient_id, birth_date="1980-01-01", gender="F",
        )

        # HbA1c from 30 days ago (within 90-day window)
        await _insert_fact(
            session,
            patient_id=patient_id,
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="7.2",
            unit="%",
            start_date=NOW - timedelta(days=30),
        )
        await session.commit()

        from app.schemas.trial import TrialCreate
        from app.models.trial import TrialPhase, TrialStatus

        trial = trial_service.create_trial(TrialCreate(
            name="Temporal Test Trial 2",
            sponsor="Test",
            phase=TrialPhase.PHASE_3,
            status=TrialStatus.RECRUITING,
            inclusion_criteria={
                "criteria": [
                    {
                        "criterion_type": "measurement",
                        "name": "Recent HbA1c",
                        "codes": [
                            {"code": "4548-4", "display": "Hemoglobin A1c"},
                        ],
                        "code_system": "LOINC",
                        "temporal_window_days": 90,
                    },
                ],
                "root_operator": "AND",
            },
            exclusion_criteria={"criteria": [], "root_operator": "AND"},
            enrollment_target=100,
        ))

        eligibility = await trial_service.check_patient_eligibility(
            str(trial.id), patient_id, session=session,
        )
        assert eligibility is not None
        hba1c_detail = next(
            (cr for cr in eligibility.criteria_details if cr.criterion_name == "Recent HbA1c"),
            None,
        )
        assert hba1c_detail is not None
        assert hba1c_detail.status == "PASS"

    @pytest.mark.asyncio
    async def test_criterion_without_temporal_ignores_dates(
        self, session, trial_service,
    ):
        """A criterion WITHOUT temporal config should match regardless of age."""
        patient_id = "TEMP-INTEG-003"
        await _insert_patient_node(
            session, patient_id=patient_id, birth_date="1980-01-01", gender="M",
        )

        # Old HbA1c (no temporal constraint -> should still match)
        await _insert_fact(
            session,
            patient_id=patient_id,
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="7.2",
            unit="%",
            start_date=NOW - timedelta(days=500),
        )
        await session.commit()

        from app.schemas.trial import TrialCreate
        from app.models.trial import TrialPhase, TrialStatus

        trial = trial_service.create_trial(TrialCreate(
            name="No Temporal Trial",
            sponsor="Test",
            phase=TrialPhase.PHASE_3,
            status=TrialStatus.RECRUITING,
            inclusion_criteria={
                "criteria": [
                    {
                        "criterion_type": "measurement",
                        "name": "HbA1c",
                        "codes": [
                            {"code": "4548-4", "display": "Hemoglobin A1c"},
                        ],
                        "code_system": "LOINC",
                        # No temporal_window_days
                    },
                ],
                "root_operator": "AND",
            },
            exclusion_criteria={"criteria": [], "root_operator": "AND"},
            enrollment_target=100,
        ))

        eligibility = await trial_service.check_patient_eligibility(
            str(trial.id), patient_id, session=session,
        )
        assert eligibility is not None
        hba1c_detail = next(
            (cr for cr in eligibility.criteria_details if cr.criterion_name == "HbA1c"),
            None,
        )
        assert hba1c_detail is not None
        assert hba1c_detail.status == "PASS"


# =============================================================================
# 12. Realistic trial criteria
# =============================================================================


class TestRealisticTrialCriteria:
    """Tests with realistic trial criteria from the demo trials."""

    def test_eylea_hd_hba1c_90_days(self, temporal_service):
        """EYLEA HD: HbA1c measured within 90 days of screening."""
        # Recent HbA1c (60 days ago)
        recent = FakeFact(start_date=NOW - timedelta(days=60))
        # Old HbA1c (150 days ago)
        old = FakeFact(start_date=NOW - timedelta(days=150))

        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [recent, old], criterion, reference_date=NOW,
        )
        assert result.status == TemporalStatus.MET
        assert recent.id in result.matched_fact_ids
        assert old.id in result.excluded_fact_ids

    def test_dupixent_ad_diagnosis_1_year(self, temporal_service):
        """Dupixent: Atopic dermatitis diagnosis for >= 1 year."""
        # Diagnosed 2 years ago, still active
        long_ad = FakeFact(start_date=NOW - timedelta(days=730), end_date=None)
        # Diagnosed 3 months ago
        short_ad = FakeFact(start_date=NOW - timedelta(days=90), end_date=None)

        criterion = TemporalCriterion(
            direction=TemporalDirection.ACTIVE,
            min_duration_days=365,
        )
        result_long = temporal_service.apply_temporal_filter(
            [long_ad], criterion, reference_date=NOW,
        )
        result_short = temporal_service.apply_temporal_filter(
            [short_ad], criterion, reference_date=NOW,
        )
        assert result_long.status == TemporalStatus.MET
        assert result_short.status == TemporalStatus.NOT_MET

    def test_libtayo_no_prior_pd1_12_months(self, temporal_service):
        """Libtayo: No prior anti-PD-1 therapy within 12 months."""
        # Treatment 6 months ago (within exclusion window)
        recent_tx = FakeFact(start_date=NOW - timedelta(days=180))
        # Treatment 18 months ago (outside exclusion window)
        old_tx = FakeFact(start_date=NOW - timedelta(days=540))

        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=365,
        )
        result_recent = temporal_service.apply_temporal_filter(
            [recent_tx], criterion, reference_date=NOW,
        )
        result_old = temporal_service.apply_temporal_filter(
            [old_tx], criterion, reference_date=NOW,
        )
        # Recent treatment matches (meaning exclusion WOULD apply)
        assert result_recent.status == TemporalStatus.MET
        # Old treatment doesn't match (exclusion would NOT apply)
        assert result_old.status == TemporalStatus.NOT_MET


# =============================================================================
# 13. Schema validation tests
# =============================================================================


class TestSchemaValidation:
    """Tests for temporal schema validation."""

    def test_temporal_criterion_defaults(self):
        """TemporalCriterion should have sensible defaults."""
        tc = TemporalCriterion(direction=TemporalDirection.WITHIN_LAST)
        assert tc.reference_point == TemporalReferencePoint.NOW
        assert tc.missing_date_policy == MissingDatePolicy.UNKNOWN
        assert tc.time_window_days is None

    def test_temporal_criterion_between_requires_dates(self):
        """BETWEEN direction with explicit dates."""
        tc = TemporalCriterion(
            direction=TemporalDirection.BETWEEN,
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        assert tc.start_date is not None
        assert tc.end_date is not None

    def test_temporal_result_structure(self, temporal_service):
        """TemporalResult should have correct structure after filtering."""
        fact = FakeFact(start_date=NOW - timedelta(days=10))
        criterion = TemporalCriterion(
            direction=TemporalDirection.WITHIN_LAST,
            time_window_days=90,
        )
        result = temporal_service.apply_temporal_filter(
            [fact], criterion, reference_date=NOW,
        )
        assert isinstance(result, TemporalResult)
        assert result.criterion == criterion
        assert result.total_facts_evaluated == 1
        assert result.window_start is not None
        assert result.window_end is not None

    def test_temporal_filter_config_defaults(self):
        """TemporalFilterConfig should have correct defaults."""
        config = TemporalFilterConfig()
        assert config.default_lookback_days == 365
        assert config.require_dates is False
        assert config.missing_date_policy == MissingDatePolicy.UNKNOWN


# =============================================================================
# 14. _parse_temporal_config helper tests
# =============================================================================


class TestParseTemporalConfig:
    """Tests for TrialEligibilityService._parse_temporal_config."""

    def test_no_temporal_config(self, trial_service):
        """Criterion without temporal config returns None."""
        criterion = {"criterion_type": "condition", "name": "Test"}
        result = trial_service._parse_temporal_config(criterion)
        assert result is None

    def test_temporal_window_days_shorthand(self, trial_service):
        """temporal_window_days shorthand creates WITHIN_LAST criterion."""
        criterion = {
            "criterion_type": "measurement",
            "name": "HbA1c",
            "temporal_window_days": 90,
        }
        result = trial_service._parse_temporal_config(criterion)
        assert result is not None
        assert result.direction == TemporalDirection.WITHIN_LAST
        assert result.time_window_days == 90

    def test_full_temporal_dict(self, trial_service):
        """Full temporal dict should be parsed correctly."""
        criterion = {
            "criterion_type": "condition",
            "name": "Active AD",
            "temporal": {
                "direction": "active",
                "min_duration_days": 365,
            },
        }
        result = trial_service._parse_temporal_config(criterion)
        assert result is not None
        assert result.direction == TemporalDirection.ACTIVE
        assert result.min_duration_days == 365

    def test_invalid_temporal_dict(self, trial_service):
        """Invalid temporal dict should return None (not crash)."""
        criterion = {
            "criterion_type": "condition",
            "name": "Bad",
            "temporal": {"direction": "invalid_direction"},
        }
        result = trial_service._parse_temporal_config(criterion)
        assert result is None

    def test_invalid_temporal_window_days(self, trial_service):
        """Non-numeric temporal_window_days should return None."""
        criterion = {
            "criterion_type": "measurement",
            "name": "Test",
            "temporal_window_days": "not_a_number",
        }
        result = trial_service._parse_temporal_config(criterion)
        assert result is None
