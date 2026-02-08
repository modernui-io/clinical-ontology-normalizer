"""Referral Network Service for site-to-site patient referrals.

VP-Product-5: Manages patient referrals between sites, site matching,
enrollment workflow tracking, and network analytics for clinical trials.

Usage:
    from app.services.referral_service import get_referral_service

    service = get_referral_service()
    referral = service.create_referral(ReferralCreate(...))
    suggestions = service.suggest_sites(SiteSuggestionRequest(...))
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.referral_network import (
    ENROLLMENT_STAGE_TRANSITIONS,
    REFERRAL_STATUS_TRANSITIONS,
    EnrollmentAdvanceResponse,
    EnrollmentMilestone,
    EnrollmentStage,
    EnrollmentTracking,
    NetworkAnalytics,
    ReferralCreate,
    ReferralPriority,
    ReferralResponse,
    ReferralStatus,
    ReferralUpdate,
    SiteReferralMetrics,
    SiteSuggestion,
    SiteSuggestionRequest,
    SiteSuggestionResponse,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Internal data structures
# ==============================================================================


class _ReferralRecord:
    """Internal referral storage record."""

    def __init__(self, referral_id: str, create: ReferralCreate):
        now = datetime.now(timezone.utc).isoformat()
        self.id = referral_id
        self.patient_id = create.patient_id
        self.source_site_id = create.source_site_id
        self.destination_site_id = create.destination_site_id
        self.trial_id = create.trial_id
        self.referring_provider = create.referring_provider
        self.reason = create.reason
        self.status = ReferralStatus.INITIATED
        self.priority = create.priority
        self.created_at = now
        self.updated_at = now
        self.accepted_at: str | None = None
        self.completed_at: str | None = None
        self.notes = create.notes

    def to_response(self) -> ReferralResponse:
        return ReferralResponse(
            id=self.id,
            patient_id=self.patient_id,
            source_site_id=self.source_site_id,
            destination_site_id=self.destination_site_id,
            trial_id=self.trial_id,
            referring_provider=self.referring_provider,
            reason=self.reason,
            status=self.status,
            priority=self.priority,
            created_at=self.created_at,
            updated_at=self.updated_at,
            accepted_at=self.accepted_at,
            completed_at=self.completed_at,
            notes=self.notes,
        )


class _EnrollmentRecord:
    """Internal enrollment tracking record."""

    def __init__(self, patient_id: str, trial_id: str):
        now = datetime.now(timezone.utc).isoformat()
        self.patient_id = patient_id
        self.trial_id = trial_id
        self.current_stage = EnrollmentStage.CANDIDATE
        self.milestones: list[EnrollmentMilestone] = [
            EnrollmentMilestone(
                stage=EnrollmentStage.CANDIDATE,
                timestamp=now,
                notes="Patient identified as candidate",
            )
        ]
        self.created_at = now
        self.updated_at = now

    def to_tracking(self) -> EnrollmentTracking:
        tte = self._compute_time_to_enrollment()
        return EnrollmentTracking(
            patient_id=self.patient_id,
            trial_id=self.trial_id,
            current_stage=self.current_stage,
            milestones=self.milestones,
            time_to_enrollment_days=tte,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def _compute_time_to_enrollment(self) -> float | None:
        """Compute days from CANDIDATE to ENROLLED."""
        candidate_ts: str | None = None
        enrolled_ts: str | None = None
        for m in self.milestones:
            if m.stage == EnrollmentStage.CANDIDATE and candidate_ts is None:
                candidate_ts = m.timestamp
            if m.stage == EnrollmentStage.ENROLLED:
                enrolled_ts = m.timestamp
        if candidate_ts and enrolled_ts:
            c = datetime.fromisoformat(candidate_ts)
            e = datetime.fromisoformat(enrolled_ts)
            delta = (e - c).total_seconds()
            return round(delta / 86400.0, 2)
        return None


class _DemoSite:
    """Demo site record with extended attributes for matching."""

    def __init__(
        self,
        site_id: str,
        name: str,
        city: str,
        state: str,
        lat: float,
        lon: float,
        specialties: list[str],
        enrollment_capacity: int,
        current_enrollment: int,
        screening_success_rate: float,
    ):
        self.site_id = site_id
        self.name = name
        self.city = city
        self.state = state
        self.lat = lat
        self.lon = lon
        self.specialties = specialties
        self.enrollment_capacity = enrollment_capacity
        self.current_enrollment = current_enrollment
        self.screening_success_rate = screening_success_rate


# ==============================================================================
# Pre-populated demo data
# ==============================================================================

_DEMO_SITES: list[_DemoSite] = [
    _DemoSite(
        site_id="site-001",
        name="Emory Eye Center",
        city="Atlanta",
        state="GA",
        lat=33.7927,
        lon=-84.3232,
        specialties=["ophthalmology", "retinal_diseases", "macular_degeneration"],
        enrollment_capacity=50,
        current_enrollment=12,
        screening_success_rate=0.78,
    ),
    _DemoSite(
        site_id="site-002",
        name="Bascom Palmer Eye Institute",
        city="Miami",
        state="FL",
        lat=25.7883,
        lon=-80.2101,
        specialties=["ophthalmology", "retinal_diseases", "diabetic_retinopathy"],
        enrollment_capacity=60,
        current_enrollment=28,
        screening_success_rate=0.82,
    ),
    _DemoSite(
        site_id="site-003",
        name="Northwestern Dermatology",
        city="Chicago",
        state="IL",
        lat=41.8961,
        lon=-87.6178,
        specialties=["dermatology", "atopic_dermatitis", "immunology"],
        enrollment_capacity=40,
        current_enrollment=15,
        screening_success_rate=0.71,
    ),
    _DemoSite(
        site_id="site-004",
        name="Memorial Sloan Kettering Cancer Center",
        city="New York",
        state="NY",
        lat=40.7646,
        lon=-73.9566,
        specialties=["oncology", "immunotherapy", "skin_cancer", "lung_cancer"],
        enrollment_capacity=80,
        current_enrollment=52,
        screening_success_rate=0.85,
    ),
    _DemoSite(
        site_id="site-005",
        name="Mayo Clinic",
        city="Rochester",
        state="MN",
        lat=44.0225,
        lon=-92.4670,
        specialties=[
            "ophthalmology",
            "dermatology",
            "oncology",
            "immunology",
            "macular_degeneration",
        ],
        enrollment_capacity=100,
        current_enrollment=35,
        screening_success_rate=0.88,
    ),
]

# Trial-to-specialty mappings for the 3 demo trials
_TRIAL_SPECIALTIES: dict[str, list[str]] = {
    "EYLEA": ["ophthalmology", "retinal_diseases", "macular_degeneration", "diabetic_retinopathy"],
    "Dupixent": ["dermatology", "atopic_dermatitis", "immunology"],
    "Libtayo": ["oncology", "immunotherapy", "skin_cancer", "lung_cancer"],
}


def _build_demo_referrals() -> list[_ReferralRecord]:
    """Create 10 sample referrals across the demo trials."""
    referrals: list[_ReferralRecord] = []

    specs = [
        # EYLEA referrals
        ("PAT-001", "site-001", "site-002", "trial-eylea", "EYLEA", ReferralPriority.HIGH, ReferralStatus.COMPLETED),
        ("PAT-002", "site-005", "site-001", "trial-eylea", "EYLEA", ReferralPriority.NORMAL, ReferralStatus.ACCEPTED),
        ("PAT-003", "site-002", "site-005", "trial-eylea", "EYLEA", ReferralPriority.URGENT, ReferralStatus.IN_PROGRESS),
        # Dupixent referrals
        ("PAT-004", "site-003", "site-005", "trial-dupixent", "Dupixent", ReferralPriority.NORMAL, ReferralStatus.PENDING_REVIEW),
        ("PAT-005", "site-005", "site-003", "trial-dupixent", "Dupixent", ReferralPriority.HIGH, ReferralStatus.COMPLETED),
        ("PAT-006", "site-003", "site-005", "trial-dupixent", "Dupixent", ReferralPriority.LOW, ReferralStatus.DECLINED),
        ("PAT-007", "site-005", "site-003", "trial-dupixent", "Dupixent", ReferralPriority.NORMAL, ReferralStatus.INITIATED),
        # Libtayo referrals
        ("PAT-008", "site-004", "site-005", "trial-libtayo", "Libtayo", ReferralPriority.URGENT, ReferralStatus.ACCEPTED),
        ("PAT-009", "site-005", "site-004", "trial-libtayo", "Libtayo", ReferralPriority.HIGH, ReferralStatus.IN_PROGRESS),
        ("PAT-010", "site-004", "site-005", "trial-libtayo", "Libtayo", ReferralPriority.NORMAL, ReferralStatus.CANCELLED),
    ]

    for i, (patient, src, dst, trial, trial_name, priority, status) in enumerate(specs, 1):
        ref_id = f"ref-demo-{i:03d}"
        create = ReferralCreate(
            patient_id=patient,
            source_site_id=src,
            destination_site_id=dst,
            trial_id=trial,
            referring_provider=f"Dr. Demo-{i}",
            reason=f"Patient suitable for {trial_name} trial",
            priority=priority,
            notes=f"Demo referral {i} for {trial_name}",
        )
        record = _ReferralRecord(ref_id, create)
        record.status = status
        # Set timestamps for completed/accepted
        if status in (ReferralStatus.ACCEPTED, ReferralStatus.IN_PROGRESS, ReferralStatus.COMPLETED):
            record.accepted_at = record.created_at
        if status == ReferralStatus.COMPLETED:
            record.completed_at = record.created_at
        referrals.append(record)

    return referrals


# ==============================================================================
# ReferralService
# ==============================================================================


class ReferralService:
    """Manages patient referrals between sites and trials.

    Provides:
    - Referral CRUD with lifecycle management
    - Site matching/suggestion based on proximity, capacity, performance, specialty
    - Enrollment workflow tracking with milestone timestamps
    - Network analytics (referral volume, acceptance rates, conversion)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Referrals keyed by referral ID
        self._referrals: dict[str, _ReferralRecord] = {}
        # Enrollment tracking keyed by (patient_id, trial_id)
        self._enrollments: dict[tuple[str, str], _EnrollmentRecord] = {}
        # Demo sites keyed by site_id
        self._sites: dict[str, _DemoSite] = {s.site_id: s for s in _DEMO_SITES}
        # Load demo referrals
        for ref in _build_demo_referrals():
            self._referrals[ref.id] = ref

    # ------------------------------------------------------------------
    # Referral CRUD
    # ------------------------------------------------------------------

    def create_referral(self, create: ReferralCreate) -> ReferralResponse:
        """Create a new referral record."""
        with self._lock:
            referral_id = str(uuid4())
            record = _ReferralRecord(referral_id, create)
            self._referrals[referral_id] = record
            logger.info(
                "Created referral %s: patient=%s, src=%s, dst=%s, trial=%s",
                referral_id,
                create.patient_id,
                create.source_site_id,
                create.destination_site_id,
                create.trial_id,
            )
            return record.to_response()

    def get_referral(self, referral_id: str) -> ReferralResponse | None:
        """Get a referral by ID."""
        with self._lock:
            record = self._referrals.get(referral_id)
            if record is None:
                return None
            return record.to_response()

    def list_referrals(
        self,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: ReferralStatus | None = None,
        patient_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReferralResponse], int]:
        """List referrals with optional filters.

        Returns:
            Tuple of (filtered referral list, total count).
        """
        with self._lock:
            filtered = list(self._referrals.values())

            if trial_id:
                filtered = [r for r in filtered if r.trial_id == trial_id]
            if site_id:
                filtered = [
                    r for r in filtered
                    if r.source_site_id == site_id or r.destination_site_id == site_id
                ]
            if status:
                filtered = [r for r in filtered if r.status == status]
            if patient_id:
                filtered = [r for r in filtered if r.patient_id == patient_id]

            total = len(filtered)
            # Sort by created_at descending
            filtered.sort(key=lambda r: r.created_at, reverse=True)
            page = filtered[offset : offset + limit]
            return [r.to_response() for r in page], total

    def update_referral(
        self, referral_id: str, update: ReferralUpdate
    ) -> ReferralResponse | None:
        """Update a referral. Validates status transitions.

        Returns:
            Updated referral response, or None if not found.

        Raises:
            ValueError: If the status transition is invalid.
        """
        with self._lock:
            record = self._referrals.get(referral_id)
            if record is None:
                return None

            now = datetime.now(timezone.utc).isoformat()

            # Validate status transition
            if update.status is not None and update.status != record.status:
                allowed = REFERRAL_STATUS_TRANSITIONS.get(record.status, [])
                if update.status not in allowed:
                    raise ValueError(
                        f"Invalid status transition: {record.status.value} -> {update.status.value}. "
                        f"Allowed: {[s.value for s in allowed]}"
                    )
                record.status = update.status
                record.updated_at = now

                # Track milestone timestamps
                if update.status == ReferralStatus.ACCEPTED:
                    record.accepted_at = now
                elif update.status == ReferralStatus.COMPLETED:
                    record.completed_at = now

            if update.priority is not None:
                record.priority = update.priority
                record.updated_at = now
            if update.notes is not None:
                record.notes = update.notes
                record.updated_at = now
            if update.referring_provider is not None:
                record.referring_provider = update.referring_provider
                record.updated_at = now
            if update.reason is not None:
                record.reason = update.reason
                record.updated_at = now

            logger.info("Updated referral %s: status=%s", referral_id, record.status.value)
            return record.to_response()

    # ------------------------------------------------------------------
    # Site matching
    # ------------------------------------------------------------------

    def suggest_sites(self, request: SiteSuggestionRequest) -> SiteSuggestionResponse:
        """Suggest best sites for a patient/trial based on composite scoring.

        Scoring factors:
        - Geographic proximity (distance scoring, 30% weight)
        - Site capacity (enrollment headroom, 25% weight)
        - Site performance (historical screening success, 25% weight)
        - Specialty match (capabilities vs trial requirements, 20% weight)
        """
        with self._lock:
            trial_id = request.trial_id
            suggestions: list[SiteSuggestion] = []

            # Determine trial specialties needed
            trial_specialties = self._get_trial_specialties(trial_id)

            for site in self._sites.values():
                distance_score = self._compute_distance_score(
                    request.patient_lat, request.patient_lon, site.lat, site.lon
                )
                capacity_score = self._compute_capacity_score(site)
                performance_score = site.screening_success_rate
                specialty_score = self._compute_specialty_score(
                    site.specialties, trial_specialties
                )

                # Weighted composite
                overall = (
                    0.30 * distance_score
                    + 0.25 * capacity_score
                    + 0.25 * performance_score
                    + 0.20 * specialty_score
                )

                reasoning_parts = []
                if specialty_score > 0.5:
                    matching = set(site.specialties) & set(trial_specialties)
                    reasoning_parts.append(f"Specialty match: {', '.join(matching)}")
                if capacity_score > 0.5:
                    headroom = site.enrollment_capacity - site.current_enrollment
                    reasoning_parts.append(f"{headroom} enrollment slots available")
                if performance_score > 0.75:
                    reasoning_parts.append(
                        f"High screening success rate ({performance_score:.0%})"
                    )

                suggestions.append(
                    SiteSuggestion(
                        site_id=site.site_id,
                        site_name=site.name,
                        city=site.city,
                        state=site.state,
                        overall_score=round(overall, 4),
                        distance_score=round(distance_score, 4),
                        capacity_score=round(capacity_score, 4),
                        performance_score=round(performance_score, 4),
                        specialty_score=round(specialty_score, 4),
                        current_enrollment=site.current_enrollment,
                        enrollment_target=site.enrollment_capacity,
                        reasoning="; ".join(reasoning_parts) if reasoning_parts else None,
                    )
                )

            # Sort by overall_score descending
            suggestions.sort(key=lambda s: s.overall_score, reverse=True)
            truncated = suggestions[: request.max_results]

            return SiteSuggestionResponse(
                patient_id=request.patient_id,
                trial_id=request.trial_id,
                suggestions=truncated,
                total_sites_evaluated=len(self._sites),
            )

    def _get_trial_specialties(self, trial_id: str) -> list[str]:
        """Map trial ID to required specialties."""
        # Check well-known demo trial IDs
        trial_lower = trial_id.lower()
        for key, specs in _TRIAL_SPECIALTIES.items():
            if key.lower() in trial_lower:
                return specs
        # Default: return broad list so all sites get some score
        return ["general_medicine"]

    @staticmethod
    def _compute_distance_score(
        patient_lat: float | None,
        patient_lon: float | None,
        site_lat: float,
        site_lon: float,
    ) -> float:
        """Compute geographic proximity score (1.0 = very close, 0.0 = very far).

        Uses Haversine distance. If patient coordinates not provided, returns 0.5.
        """
        if patient_lat is None or patient_lon is None:
            return 0.5  # neutral score when location unknown

        # Haversine formula
        R = 6371.0  # Earth radius in km
        lat1, lat2 = math.radians(patient_lat), math.radians(site_lat)
        dlat = math.radians(site_lat - patient_lat)
        dlon = math.radians(site_lon - patient_lon)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = R * c

        # Score: exponential decay. 0 km => 1.0, 500 km => ~0.37, 1500 km => ~0.05
        score = math.exp(-distance_km / 500.0)
        return round(min(1.0, max(0.0, score)), 4)

    @staticmethod
    def _compute_capacity_score(site: _DemoSite) -> float:
        """Compute capacity score based on enrollment headroom."""
        if site.enrollment_capacity <= 0:
            return 0.0
        headroom = site.enrollment_capacity - site.current_enrollment
        if headroom <= 0:
            return 0.0
        # Fraction of capacity remaining
        return round(headroom / site.enrollment_capacity, 4)

    @staticmethod
    def _compute_specialty_score(
        site_specialties: list[str], trial_specialties: list[str]
    ) -> float:
        """Compute specialty match score (Jaccard-like)."""
        if not trial_specialties:
            return 0.5
        site_set = set(site_specialties)
        trial_set = set(trial_specialties)
        intersection = site_set & trial_set
        if not intersection:
            return 0.0
        # Fraction of trial specialties covered by the site
        return round(len(intersection) / len(trial_set), 4)

    # ------------------------------------------------------------------
    # Enrollment workflow
    # ------------------------------------------------------------------

    def get_enrollment(
        self, patient_id: str, trial_id: str
    ) -> EnrollmentTracking | None:
        """Get enrollment tracking for a patient/trial pair."""
        with self._lock:
            record = self._enrollments.get((patient_id, trial_id))
            if record is None:
                return None
            return record.to_tracking()

    def create_enrollment(
        self, patient_id: str, trial_id: str
    ) -> EnrollmentTracking:
        """Create or retrieve enrollment tracking for a patient/trial pair."""
        with self._lock:
            key = (patient_id, trial_id)
            if key not in self._enrollments:
                self._enrollments[key] = _EnrollmentRecord(patient_id, trial_id)
                logger.info(
                    "Created enrollment tracking: patient=%s, trial=%s",
                    patient_id,
                    trial_id,
                )
            return self._enrollments[key].to_tracking()

    def advance_enrollment(
        self, patient_id: str, trial_id: str, notes: str | None = None
    ) -> EnrollmentAdvanceResponse | None:
        """Advance enrollment to the next stage.

        Returns:
            EnrollmentAdvanceResponse if successful, None if enrollment not found.

        Raises:
            ValueError: If the patient is at a terminal stage or transition is invalid.
        """
        with self._lock:
            key = (patient_id, trial_id)
            record = self._enrollments.get(key)
            if record is None:
                return None

            current = record.current_stage
            allowed = ENROLLMENT_STAGE_TRANSITIONS.get(current, [])
            # Filter out WITHDRAWN -- advance always goes forward
            forward_stages = [s for s in allowed if s != EnrollmentStage.WITHDRAWN]

            if not forward_stages:
                raise ValueError(
                    f"Cannot advance enrollment from terminal stage: {current.value}"
                )

            next_stage = forward_stages[0]
            now = datetime.now(timezone.utc).isoformat()

            milestone = EnrollmentMilestone(
                stage=next_stage,
                timestamp=now,
                notes=notes,
            )

            record.current_stage = next_stage
            record.milestones.append(milestone)
            record.updated_at = now

            logger.info(
                "Advanced enrollment: patient=%s, trial=%s, %s -> %s",
                patient_id,
                trial_id,
                current.value,
                next_stage.value,
            )

            return EnrollmentAdvanceResponse(
                patient_id=patient_id,
                trial_id=trial_id,
                previous_stage=current,
                current_stage=next_stage,
                milestone=milestone,
            )

    def withdraw_enrollment(
        self, patient_id: str, trial_id: str, notes: str | None = None
    ) -> EnrollmentAdvanceResponse | None:
        """Withdraw a patient from enrollment.

        Returns:
            EnrollmentAdvanceResponse if successful, None if not found.

        Raises:
            ValueError: If already withdrawn.
        """
        with self._lock:
            key = (patient_id, trial_id)
            record = self._enrollments.get(key)
            if record is None:
                return None

            current = record.current_stage
            if current == EnrollmentStage.WITHDRAWN:
                raise ValueError("Patient is already withdrawn")

            now = datetime.now(timezone.utc).isoformat()
            milestone = EnrollmentMilestone(
                stage=EnrollmentStage.WITHDRAWN,
                timestamp=now,
                notes=notes or "Patient withdrawn",
            )

            record.current_stage = EnrollmentStage.WITHDRAWN
            record.milestones.append(milestone)
            record.updated_at = now

            return EnrollmentAdvanceResponse(
                patient_id=patient_id,
                trial_id=trial_id,
                previous_stage=current,
                current_stage=EnrollmentStage.WITHDRAWN,
                milestone=milestone,
            )

    # ------------------------------------------------------------------
    # Network analytics
    # ------------------------------------------------------------------

    def get_analytics(
        self,
        trial_id: str | None = None,
        site_id: str | None = None,
    ) -> NetworkAnalytics:
        """Compute referral network analytics.

        Optionally filter by trial_id or site_id.
        """
        with self._lock:
            referrals = list(self._referrals.values())

            if trial_id:
                referrals = [r for r in referrals if r.trial_id == trial_id]
            if site_id:
                referrals = [
                    r for r in referrals
                    if r.source_site_id == site_id or r.destination_site_id == site_id
                ]

            total = len(referrals)
            active = sum(
                1 for r in referrals
                if r.status in (ReferralStatus.INITIATED, ReferralStatus.PENDING_REVIEW,
                                ReferralStatus.ACCEPTED, ReferralStatus.IN_PROGRESS)
            )
            completed = sum(1 for r in referrals if r.status == ReferralStatus.COMPLETED)
            declined = sum(1 for r in referrals if r.status == ReferralStatus.DECLINED)

            # Acceptance rate: accepted + in_progress + completed / (total - cancelled)
            non_cancelled = [r for r in referrals if r.status != ReferralStatus.CANCELLED]
            accepted_total = sum(
                1 for r in non_cancelled
                if r.status in (
                    ReferralStatus.ACCEPTED,
                    ReferralStatus.IN_PROGRESS,
                    ReferralStatus.COMPLETED,
                )
            )
            acceptance_rate = (
                accepted_total / len(non_cancelled) if non_cancelled else 0.0
            )

            # Conversion rate: completed / total
            conversion_rate = completed / total if total > 0 else 0.0

            # Average times
            avg_accept = self._avg_time_to_accept(referrals)
            avg_complete = self._avg_time_to_complete(referrals)

            # Per-site metrics
            site_ids = set()
            for r in referrals:
                site_ids.add(r.source_site_id)
                site_ids.add(r.destination_site_id)

            site_metrics_list = []
            for sid in sorted(site_ids):
                sm = self._compute_site_metrics(sid, referrals)
                site_metrics_list.append(sm)

            # Top referring sites (by referrals_sent)
            top_referring = sorted(
                site_metrics_list, key=lambda s: s.referrals_sent, reverse=True
            )[:5]

            # Volume by trial
            volume_by_trial: dict[str, int] = {}
            for r in referrals:
                volume_by_trial[r.trial_id] = volume_by_trial.get(r.trial_id, 0) + 1

            return NetworkAnalytics(
                total_referrals=total,
                total_active_referrals=active,
                total_completed_referrals=completed,
                total_declined_referrals=declined,
                overall_acceptance_rate=round(acceptance_rate, 4),
                overall_conversion_rate=round(conversion_rate, 4),
                avg_time_to_accept_hours=avg_accept,
                avg_time_to_complete_hours=avg_complete,
                site_metrics=site_metrics_list,
                top_referring_sites=top_referring,
                referral_volume_by_trial=volume_by_trial,
            )

    def _compute_site_metrics(
        self, site_id: str, referrals: list[_ReferralRecord]
    ) -> SiteReferralMetrics:
        """Compute metrics for a single site."""
        site_name = site_id
        if site_id in self._sites:
            site_name = self._sites[site_id].name

        sent = [r for r in referrals if r.source_site_id == site_id]
        received = [r for r in referrals if r.destination_site_id == site_id]

        # Acceptance rate for received referrals
        non_cancelled_received = [
            r for r in received if r.status != ReferralStatus.CANCELLED
        ]
        accepted_received = sum(
            1 for r in non_cancelled_received
            if r.status in (
                ReferralStatus.ACCEPTED,
                ReferralStatus.IN_PROGRESS,
                ReferralStatus.COMPLETED,
            )
        )
        acceptance_rate = (
            accepted_received / len(non_cancelled_received)
            if non_cancelled_received
            else 0.0
        )

        # Conversion rate: completed / total received
        completed_received = sum(
            1 for r in received if r.status == ReferralStatus.COMPLETED
        )
        conversion_rate = (
            completed_received / len(received) if received else 0.0
        )

        all_site = sent + received
        avg_accept = self._avg_time_to_accept(all_site)
        avg_complete = self._avg_time_to_complete(all_site)

        return SiteReferralMetrics(
            site_id=site_id,
            site_name=site_name,
            referrals_sent=len(sent),
            referrals_received=len(received),
            acceptance_rate=round(acceptance_rate, 4),
            avg_time_to_accept_hours=avg_accept,
            avg_time_to_complete_hours=avg_complete,
            conversion_rate=round(conversion_rate, 4),
        )

    @staticmethod
    def _avg_time_to_accept(referrals: list[_ReferralRecord]) -> float | None:
        """Average hours from creation to acceptance."""
        times = []
        for r in referrals:
            if r.accepted_at:
                created = datetime.fromisoformat(r.created_at)
                accepted = datetime.fromisoformat(r.accepted_at)
                hours = (accepted - created).total_seconds() / 3600.0
                times.append(hours)
        if not times:
            return None
        return round(sum(times) / len(times), 2)

    @staticmethod
    def _avg_time_to_complete(referrals: list[_ReferralRecord]) -> float | None:
        """Average hours from creation to completion."""
        times = []
        for r in referrals:
            if r.completed_at:
                created = datetime.fromisoformat(r.created_at)
                completed = datetime.fromisoformat(r.completed_at)
                hours = (completed - created).total_seconds() / 3600.0
                times.append(hours)
        if not times:
            return None
        return round(sum(times) / len(times), 2)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics."""
        with self._lock:
            return {
                "total_referrals": len(self._referrals),
                "total_enrollments": len(self._enrollments),
                "total_sites": len(self._sites),
                "demo_referrals": sum(
                    1 for k in self._referrals if k.startswith("ref-demo-")
                ),
            }


# ==============================================================================
# Singleton accessor
# ==============================================================================

_singleton_lock = threading.Lock()
_singleton: ReferralService | None = None


def get_referral_service() -> ReferralService:
    """Get or create the singleton ReferralService instance."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = ReferralService()
                logger.info("ReferralService initialized: %s", _singleton.get_stats())
    return _singleton
