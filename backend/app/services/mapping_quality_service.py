"""Mapping Quality Metrics Service.

CTO-4: OMOP Mapping Quality - calculates coverage, confidence distribution,
unmapped term analysis, domain coverage, ambiguity rates, and source distribution
by querying the Mention and MentionConceptCandidate tables.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mention import Mention, MentionConceptCandidate
from app.schemas.base import Domain
from app.schemas.mapping_quality import (
    ConfidenceBucket,
    DomainCoverage,
    MappingQualityReport,
    MappingTrendPoint,
    MappingTrendReport,
    SourceDistribution,
    UnmappedTerm,
)

logger = logging.getLogger(__name__)

# Confidence score bucket boundaries for the histogram
_BUCKET_BOUNDARIES = [
    (0.0, 0.1),
    (0.1, 0.2),
    (0.2, 0.3),
    (0.3, 0.4),
    (0.4, 0.5),
    (0.5, 0.6),
    (0.6, 0.7),
    (0.7, 0.8),
    (0.8, 0.9),
    (0.9, 1.0),
]


class MappingQualityService:
    """Service for computing OMOP mapping quality metrics.

    Queries the mentions and mention_concept_candidates tables to produce
    coverage statistics, confidence distributions, unmapped term rankings,
    and per-domain breakdowns.
    """

    async def get_mapping_quality_report(
        self,
        session: AsyncSession,
        *,
        domain_filter: str | None = None,
    ) -> MappingQualityReport:
        """Build a comprehensive mapping quality report.

        Args:
            session: Async database session.
            domain_filter: Optional domain to filter by (e.g. 'condition').

        Returns:
            MappingQualityReport with coverage, distribution, and ambiguity data.
        """
        # 1. Total mentions
        total_q = select(func.count(Mention.id))
        total_result = await session.execute(total_q)
        total_mentions: int = total_result.scalar() or 0

        # 2. Mentions with at least one candidate (mapped)
        mapped_subq = (
            select(MentionConceptCandidate.mention_id)
            .distinct()
            .subquery()
        )
        mapped_q = select(func.count()).select_from(mapped_subq)
        mapped_result = await session.execute(mapped_q)
        mapped_mentions: int = mapped_result.scalar() or 0

        # 3. Overall coverage
        overall_coverage = (
            (mapped_mentions / total_mentions * 100.0) if total_mentions > 0 else 0.0
        )

        # 4. Ambiguity: mentions with >1 candidate
        ambig_subq = (
            select(
                MentionConceptCandidate.mention_id,
                func.count(MentionConceptCandidate.id).label("cnt"),
            )
            .group_by(MentionConceptCandidate.mention_id)
            .having(func.count(MentionConceptCandidate.id) > 1)
            .subquery()
        )
        ambig_q = select(func.count()).select_from(ambig_subq)
        ambig_result = await session.execute(ambig_q)
        ambiguous_count: int = ambig_result.scalar() or 0
        ambiguity_rate = (
            (ambiguous_count / total_mentions * 100.0) if total_mentions > 0 else 0.0
        )

        # 5. Domain coverage
        domain_coverage = await self.get_mapping_coverage_by_domain(session)
        if domain_filter:
            domain_coverage = [
                d for d in domain_coverage if d.domain == domain_filter
            ]

        # 6. Confidence distribution
        confidence_distribution = await self._get_confidence_distribution(session)

        # 7. Source distribution
        source_distribution = await self._get_source_distribution(session)

        return MappingQualityReport(
            total_mentions=total_mentions,
            mapped_mentions=mapped_mentions,
            overall_coverage=round(overall_coverage, 2),
            ambiguity_rate=round(ambiguity_rate, 2),
            domain_coverage=domain_coverage,
            confidence_distribution=confidence_distribution,
            source_distribution=source_distribution,
        )

    async def get_unmapped_terms(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
        domain: str | None = None,
    ) -> list[UnmappedTerm]:
        """Get the top unmapped terms sorted by frequency.

        Finds mentions that have zero concept candidates.

        Args:
            session: Async database session.
            limit: Max number of unmapped terms to return.
            domain: Optional domain filter (not applicable for truly unmapped,
                     but included for API consistency).

        Returns:
            List of UnmappedTerm sorted by frequency descending.
        """
        # Subquery: mention_ids that have at least one candidate
        has_candidate = (
            select(MentionConceptCandidate.mention_id)
            .distinct()
            .subquery()
        )

        # Mentions without any candidate
        unmapped_q = (
            select(
                func.lower(Mention.text).label("term"),
                func.count(Mention.id).label("freq"),
            )
            .where(Mention.id.notin_(select(has_candidate.c.mention_id)))
            .group_by(func.lower(Mention.text))
            .order_by(func.count(Mention.id).desc())
            .limit(limit)
        )

        result = await session.execute(unmapped_q)
        rows = result.all()

        return [
            UnmappedTerm(
                term_text=row.term,
                frequency=row.freq,
                domain=domain,
                suggested_concepts=[],
            )
            for row in rows
        ]

    async def get_mapping_coverage_by_domain(
        self,
        session: AsyncSession,
    ) -> list[DomainCoverage]:
        """Get per-domain mapping coverage statistics.

        Groups MentionConceptCandidates by domain_id and computes coverage
        relative to all mentions.

        Args:
            session: Async database session.

        Returns:
            List of DomainCoverage, one per domain with data.
        """
        # Total mentions (we need this to detect unmapped)
        total_q = select(func.count(Mention.id))
        total_result = await session.execute(total_q)
        total_mentions: int = total_result.scalar() or 0

        if total_mentions == 0:
            return []

        # Per-domain stats from candidates (using rank=1 or best candidate)
        domain_q = (
            select(
                MentionConceptCandidate.domain_id,
                func.count(func.distinct(MentionConceptCandidate.mention_id)).label("mapped"),
                func.avg(MentionConceptCandidate.score).label("avg_score"),
            )
            .group_by(MentionConceptCandidate.domain_id)
        )
        result = await session.execute(domain_q)
        rows = result.all()

        coverages = []
        for row in rows:
            domain_name = row.domain_id.value if isinstance(row.domain_id, Domain) else str(row.domain_id)
            mapped = row.mapped
            avg_score = float(row.avg_score) if row.avg_score is not None else 0.0
            coverage_pct = mapped / total_mentions * 100.0

            coverages.append(
                DomainCoverage(
                    domain=domain_name,
                    total_mentions=total_mentions,
                    mapped_mentions=mapped,
                    coverage_pct=round(coverage_pct, 2),
                    avg_confidence=round(avg_score, 4),
                )
            )

        return sorted(coverages, key=lambda c: c.coverage_pct, reverse=True)

    async def get_mapping_trends(
        self,
        session: AsyncSession,
        *,
        days: int = 30,
    ) -> MappingTrendReport:
        """Get mapping quality trends over time.

        Groups mentions by creation date and computes daily coverage.

        Args:
            session: Async database session.
            days: Number of days to look back (default 30).

        Returns:
            MappingTrendReport with daily data points.
        """
        cutoff = date.today() - timedelta(days=days)

        # Daily mention counts
        daily_mentions_q = (
            select(
                func.date(Mention.created_at).label("day"),
                func.count(Mention.id).label("total"),
            )
            .where(func.date(Mention.created_at) >= cutoff)
            .group_by(func.date(Mention.created_at))
            .order_by(func.date(Mention.created_at))
        )
        mentions_result = await session.execute(daily_mentions_q)
        daily_mentions = {str(row.day): row.total for row in mentions_result.all()}

        # Daily mapped mention counts (mentions with candidates, by mention created_at)
        daily_mapped_q = (
            select(
                func.date(Mention.created_at).label("day"),
                func.count(func.distinct(MentionConceptCandidate.mention_id)).label("mapped"),
                func.avg(MentionConceptCandidate.score).label("avg_conf"),
            )
            .join(MentionConceptCandidate, MentionConceptCandidate.mention_id == Mention.id)
            .where(func.date(Mention.created_at) >= cutoff)
            .group_by(func.date(Mention.created_at))
            .order_by(func.date(Mention.created_at))
        )
        mapped_result = await session.execute(daily_mapped_q)
        daily_mapped: dict[str, tuple[int, float]] = {}
        for row in mapped_result.all():
            daily_mapped[str(row.day)] = (
                row.mapped,
                float(row.avg_conf) if row.avg_conf is not None else 0.0,
            )

        # Build data points
        data_points = []
        for day_str, total in sorted(daily_mentions.items()):
            mapped_count, avg_conf = daily_mapped.get(day_str, (0, 0.0))
            coverage = (mapped_count / total * 100.0) if total > 0 else 0.0
            data_points.append(
                MappingTrendPoint(
                    date=day_str,
                    coverage_pct=round(coverage, 2),
                    total_mentions=total,
                    mapped_mentions=mapped_count,
                    avg_confidence=round(avg_conf, 4),
                )
            )

        return MappingTrendReport(
            period_days=days,
            data_points=data_points,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_confidence_distribution(
        self, session: AsyncSession
    ) -> list[ConfidenceBucket]:
        """Build a histogram of candidate confidence scores."""
        # Get all scores
        scores_q = select(MentionConceptCandidate.score)
        result = await session.execute(scores_q)
        scores = [row[0] for row in result.all()]

        total = len(scores)
        if total == 0:
            return [
                ConfidenceBucket(
                    range_label=f"{lo:.1f}-{hi:.1f}",
                    count=0,
                    percentage=0.0,
                )
                for lo, hi in _BUCKET_BOUNDARIES
            ]

        # Count per bucket
        buckets: list[ConfidenceBucket] = []
        for lo, hi in _BUCKET_BOUNDARIES:
            # Include upper bound for the last bucket [0.9, 1.0]
            if hi == 1.0:
                count = sum(1 for s in scores if lo <= s <= hi)
            else:
                count = sum(1 for s in scores if lo <= s < hi)
            buckets.append(
                ConfidenceBucket(
                    range_label=f"{lo:.1f}-{hi:.1f}",
                    count=count,
                    percentage=round(count / total * 100.0, 2),
                )
            )
        return buckets

    async def _get_source_distribution(
        self, session: AsyncSession
    ) -> list[SourceDistribution]:
        """Compute distribution of mapping methods/sources."""
        source_q = (
            select(
                MentionConceptCandidate.method,
                func.count(MentionConceptCandidate.id).label("cnt"),
            )
            .group_by(MentionConceptCandidate.method)
            .order_by(func.count(MentionConceptCandidate.id).desc())
        )
        result = await session.execute(source_q)
        rows = result.all()

        total = sum(row.cnt for row in rows)
        if total == 0:
            return []

        return [
            SourceDistribution(
                source=row.method,
                count=row.cnt,
                percentage=round(row.cnt / total * 100.0, 2),
            )
            for row in rows
        ]


# Module-level singleton
_service: MappingQualityService | None = None


def get_mapping_quality_service() -> MappingQualityService:
    """Get or create the mapping quality service singleton."""
    global _service
    if _service is None:
        _service = MappingQualityService()
    return _service


def reset_mapping_quality_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
