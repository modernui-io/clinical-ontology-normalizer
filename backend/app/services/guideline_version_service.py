"""Guideline Corpus Versioning Service (P1-012, P3-013).

Tracks guideline metadata including version, source organization,
publication date, and expiration. Provides staleness checking so that
clinical agent responses can flag when underlying guidelines are outdated.

P3-013 additions:
  - check_all_guidelines_freshness() -- bulk freshness scan
  - get_guidelines_needing_review() -- approaching-stale within 90 days
  - GuidelineAlert model + generate_alerts() -- actionable notifications

Staleness rules (configurable via GUIDELINE_STALENESS_DAYS env var):
  - Current: published within staleness threshold (default 730 days / 2 years)
  - Stale: older than staleness threshold
  - Expired: older than 5 years (1825 days)
  - Superseded: explicitly replaced by a newer version
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import ClassVar

logger = logging.getLogger(__name__)

# Default: guidelines older than 2 years are stale
DEFAULT_STALENESS_DAYS = 730
# Guidelines older than 5 years are expired
EXPIRY_DAYS = 1825
# P3-013: alert when a guideline is within this many days of going stale
APPROACHING_STALE_DAYS = 90


class GuidelineStatus(Enum):
    """Lifecycle status of a clinical guideline."""

    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


@dataclass
class GuidelineMetadata:
    """Metadata for a clinical guideline in the corpus."""

    guideline_id: str
    title: str
    version: str
    source_org: str
    published_date: date
    expiry_date: date | None = None
    last_checked: date | None = None
    status: GuidelineStatus = GuidelineStatus.CURRENT
    superseded_by: str | None = None


@dataclass
class GuidelineFreshnessResult:
    """Result of a guideline freshness check."""

    guideline_id: str
    title: str
    status: GuidelineStatus
    days_since_published: int
    staleness_threshold_days: int
    message: str


@dataclass
class GuidelineCorpusInfo:
    """Summary info about the guideline corpus."""

    total_guidelines: int
    current_count: int
    stale_count: int
    expired_count: int
    superseded_count: int
    staleness_threshold_days: int
    guidelines: list[GuidelineMetadata] = field(default_factory=list)


class GuidelineAlertType(Enum):
    """P3-013: Types of guideline freshness alerts."""

    APPROACHING_STALE = "approaching_stale"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass
class GuidelineAlert:
    """P3-013: Actionable alert for a guideline requiring attention."""

    guideline_id: str
    title: str
    alert_type: GuidelineAlertType
    days_until_stale: int | None
    owner_email: str | None = None


# ============================================================================
# Built-in guideline corpus metadata
# ============================================================================

_BUILTIN_GUIDELINES: list[GuidelineMetadata] = [
    GuidelineMetadata(
        guideline_id="ADA-2024",
        title="ADA Standards of Medical Care in Diabetes",
        version="2024",
        source_org="American Diabetes Association",
        published_date=date(2024, 1, 1),
    ),
    GuidelineMetadata(
        guideline_id="ACC-AHA-HTN-2017",
        title="ACC/AHA Guideline for High Blood Pressure in Adults",
        version="2017",
        source_org="ACC/AHA",
        published_date=date(2017, 11, 13),
    ),
    GuidelineMetadata(
        guideline_id="AHA-HF-2022",
        title="AHA/ACC/HFSA Guideline for Management of Heart Failure",
        version="2022",
        source_org="AHA/ACC/HFSA",
        published_date=date(2022, 4, 1),
    ),
    GuidelineMetadata(
        guideline_id="KDIGO-CKD-2024",
        title="KDIGO Clinical Practice Guideline for CKD",
        version="2024",
        source_org="KDIGO",
        published_date=date(2024, 3, 1),
    ),
    GuidelineMetadata(
        guideline_id="GOLD-COPD-2024",
        title="GOLD Report: Global Strategy for COPD",
        version="2024",
        source_org="GOLD",
        published_date=date(2024, 1, 1),
    ),
    GuidelineMetadata(
        guideline_id="NCCN-BREAST-2023",
        title="NCCN Clinical Practice Guidelines: Breast Cancer",
        version="2023.4",
        source_org="NCCN",
        published_date=date(2023, 9, 1),
    ),
    GuidelineMetadata(
        guideline_id="IDSA-CAP-2019",
        title="IDSA/ATS Diagnosis and Treatment of Community-Acquired Pneumonia",
        version="2019",
        source_org="IDSA/ATS",
        published_date=date(2019, 10, 1),
    ),
    GuidelineMetadata(
        guideline_id="APA-MDD-2010",
        title="APA Practice Guideline for Major Depressive Disorder",
        version="3rd Edition",
        source_org="American Psychiatric Association",
        published_date=date(2010, 10, 1),
    ),
]


class GuidelineVersionService:
    """Service for tracking guideline corpus versioning and freshness."""

    _STALENESS_ENV_VAR: ClassVar[str] = "GUIDELINE_STALENESS_DAYS"

    def __init__(
        self,
        guidelines: list[GuidelineMetadata] | None = None,
        staleness_days: int | None = None,
        today: date | None = None,
    ) -> None:
        self._guidelines: dict[str, GuidelineMetadata] = {}
        self._today = today  # injectable for testing

        # Resolve staleness threshold: explicit arg > env var > default
        if staleness_days is not None:
            self._staleness_days = staleness_days
        else:
            env_val = os.environ.get(self._STALENESS_ENV_VAR)
            if env_val is not None:
                try:
                    self._staleness_days = int(env_val)
                except ValueError:
                    logger.warning(
                        f"Invalid {self._STALENESS_ENV_VAR}='{env_val}', "
                        f"using default {DEFAULT_STALENESS_DAYS}"
                    )
                    self._staleness_days = DEFAULT_STALENESS_DAYS
            else:
                self._staleness_days = DEFAULT_STALENESS_DAYS

        # Load guidelines
        source = guidelines if guidelines is not None else _BUILTIN_GUIDELINES
        for g in source:
            self._guidelines[g.guideline_id] = g

        # Recompute statuses
        self._refresh_statuses()

        logger.info(
            f"GuidelineVersionService initialized with {len(self._guidelines)} "
            f"guidelines (staleness threshold: {self._staleness_days} days)"
        )

    @property
    def staleness_threshold_days(self) -> int:
        return self._staleness_days

    def _get_today(self) -> date:
        return self._today if self._today is not None else date.today()

    def _refresh_statuses(self) -> None:
        """Recompute status for all guidelines based on current date."""
        today = self._get_today()
        for g in self._guidelines.values():
            if g.superseded_by:
                g.status = GuidelineStatus.SUPERSEDED
                continue
            if g.expiry_date and today >= g.expiry_date:
                g.status = GuidelineStatus.EXPIRED
                continue
            age_days = (today - g.published_date).days
            if age_days >= EXPIRY_DAYS:
                g.status = GuidelineStatus.EXPIRED
            elif age_days >= self._staleness_days:
                g.status = GuidelineStatus.STALE
            else:
                g.status = GuidelineStatus.CURRENT

    def check_guideline_freshness(self, guideline_id: str) -> GuidelineFreshnessResult | None:
        """Check the freshness of a specific guideline.

        Returns None if the guideline_id is not found.
        """
        g = self._guidelines.get(guideline_id)
        if g is None:
            return None

        today = self._get_today()
        age_days = (today - g.published_date).days

        # Build message
        if g.status == GuidelineStatus.SUPERSEDED:
            msg = f"Guideline has been superseded by {g.superseded_by}."
        elif g.status == GuidelineStatus.EXPIRED:
            msg = (
                f"Guideline is expired ({age_days} days old, "
                f"threshold {EXPIRY_DAYS} days). Review for updated version."
            )
        elif g.status == GuidelineStatus.STALE:
            msg = (
                f"Guideline may be outdated ({age_days} days old, "
                f"staleness threshold {self._staleness_days} days)."
            )
        else:
            msg = f"Guideline is current ({age_days} days old)."

        return GuidelineFreshnessResult(
            guideline_id=guideline_id,
            title=g.title,
            status=g.status,
            days_since_published=age_days,
            staleness_threshold_days=self._staleness_days,
            message=msg,
        )

    def get_guideline_version_info(self) -> GuidelineCorpusInfo:
        """Return summary of the entire guideline corpus."""
        self._refresh_statuses()

        current = stale = expired = superseded = 0
        for g in self._guidelines.values():
            if g.status == GuidelineStatus.CURRENT:
                current += 1
            elif g.status == GuidelineStatus.STALE:
                stale += 1
            elif g.status == GuidelineStatus.EXPIRED:
                expired += 1
            elif g.status == GuidelineStatus.SUPERSEDED:
                superseded += 1

        return GuidelineCorpusInfo(
            total_guidelines=len(self._guidelines),
            current_count=current,
            stale_count=stale,
            expired_count=expired,
            superseded_count=superseded,
            staleness_threshold_days=self._staleness_days,
            guidelines=list(self._guidelines.values()),
        )

    # ------------------------------------------------------------------
    # P3-013: Stale-guideline detection and alert generation
    # ------------------------------------------------------------------

    def check_all_guidelines_freshness(self) -> list[GuidelineFreshnessResult]:
        """Return freshness results for all stale or expired guidelines."""
        self._refresh_statuses()
        results: list[GuidelineFreshnessResult] = []
        for g in self._guidelines.values():
            if g.status in (GuidelineStatus.STALE, GuidelineStatus.EXPIRED):
                result = self.check_guideline_freshness(g.guideline_id)
                if result is not None:
                    results.append(result)
        return results

    def get_guidelines_needing_review(self) -> list[GuidelineFreshnessResult]:
        """Return guidelines approaching staleness (within APPROACHING_STALE_DAYS).

        These are guidelines that are still CURRENT but will become stale
        within the approaching-stale window (default 90 days).
        """
        self._refresh_statuses()
        today = self._get_today()
        results: list[GuidelineFreshnessResult] = []
        for g in self._guidelines.values():
            if g.status != GuidelineStatus.CURRENT:
                continue
            age_days = (today - g.published_date).days
            days_until_stale = self._staleness_days - age_days
            if 0 < days_until_stale <= APPROACHING_STALE_DAYS:
                result = self.check_guideline_freshness(g.guideline_id)
                if result is not None:
                    results.append(result)
        return results

    def generate_alerts(self) -> list[GuidelineAlert]:
        """Generate actionable alerts for all guidelines needing attention.

        Returns alerts for:
        - APPROACHING_STALE: current but within 90 days of staleness
        - STALE: past staleness threshold
        - EXPIRED: past expiry threshold
        """
        self._refresh_statuses()
        today = self._get_today()
        alerts: list[GuidelineAlert] = []

        for g in self._guidelines.values():
            age_days = (today - g.published_date).days
            days_until_stale = self._staleness_days - age_days

            if g.status == GuidelineStatus.EXPIRED:
                alerts.append(
                    GuidelineAlert(
                        guideline_id=g.guideline_id,
                        title=g.title,
                        alert_type=GuidelineAlertType.EXPIRED,
                        days_until_stale=None,
                        owner_email=f"{g.source_org.lower().replace('/', '-')}@content-owners.example.com",
                    )
                )
            elif g.status == GuidelineStatus.STALE:
                alerts.append(
                    GuidelineAlert(
                        guideline_id=g.guideline_id,
                        title=g.title,
                        alert_type=GuidelineAlertType.STALE,
                        days_until_stale=days_until_stale,
                        owner_email=f"{g.source_org.lower().replace('/', '-')}@content-owners.example.com",
                    )
                )
            elif g.status == GuidelineStatus.CURRENT and 0 < days_until_stale <= APPROACHING_STALE_DAYS:
                alerts.append(
                    GuidelineAlert(
                        guideline_id=g.guideline_id,
                        title=g.title,
                        alert_type=GuidelineAlertType.APPROACHING_STALE,
                        days_until_stale=days_until_stale,
                        owner_email=f"{g.source_org.lower().replace('/', '-')}@content-owners.example.com",
                    )
                )

        return alerts

    def get_guideline(self, guideline_id: str) -> GuidelineMetadata | None:
        """Look up a single guideline by ID."""
        return self._guidelines.get(guideline_id)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_instance: GuidelineVersionService | None = None


def get_guideline_version_service() -> GuidelineVersionService:
    """Get the singleton GuidelineVersionService."""
    global _instance
    if _instance is None:
        _instance = GuidelineVersionService()
    return _instance


def reset_guideline_version_service() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
