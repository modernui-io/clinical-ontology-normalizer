"""Patient Engagement and Communication Tracking Service.

Provides in-memory tracking of patient communications, engagement scoring,
campaign management, and analytics for the clinical trial recruitment
platform.

No PHI is stored in communication content -- only summaries and metadata.

Usage:
    from app.services.patient_engagement_service import (
        get_patient_engagement_service,
    )

    svc = get_patient_engagement_service()
    comm = svc.record_communication(CommunicationCreateRequest(...))
    score = svc.get_engagement_score("patient-1")
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from app.schemas.patient_engagement import (
    Campaign,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignStatus,
    ChannelEffectiveness,
    CommunicationChannel,
    CommunicationCreateRequest,
    CommunicationDirection,
    CommunicationListResponse,
    CommunicationRecord,
    CommunicationStatus,
    CommunicationTemplate,
    CommunicationUpdateRequest,
    EngagementAnalytics,
    EngagementFunnel,
    EngagementScore,
    FrequencyUnit,
    PatientPreferences,
    PreferencesUpdateRequest,
    TemplatePerformance,
    TemplateType,
    TimePeriodEffectiveness,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default communication templates
# ---------------------------------------------------------------------------

_DEFAULT_TEMPLATES: list[dict] = [
    {
        "template_type": TemplateType.SCREENING_INVITATION,
        "name": "Trial Screening Invitation",
        "description": (
            "Initial invitation for a patient to participate in "
            "clinical trial screening"
        ),
        "channel": CommunicationChannel.EMAIL,
        "subject_template": "You may qualify for a clinical trial: {trial_name}",
        "content_template": (
            "Screening invitation for {trial_name}. "
            "Please review eligibility criteria."
        ),
    },
    {
        "template_type": TemplateType.ELIGIBILITY_RESULT,
        "name": "Screening Outcome Notification",
        "description": "Notification of screening eligibility determination",
        "channel": CommunicationChannel.EMAIL,
        "subject_template": "Your screening results for {trial_name}",
        "content_template": (
            "Eligibility result notification for {trial_name}. "
            "Status: {result_status}."
        ),
    },
    {
        "template_type": TemplateType.APPOINTMENT_REMINDER,
        "name": "Site Visit Reminder",
        "description": "Reminder for an upcoming site visit or appointment",
        "channel": CommunicationChannel.SMS,
        "subject_template": "Reminder: Appointment on {appointment_date}",
        "content_template": (
            "Appointment reminder for {appointment_date} at {site_name}."
        ),
    },
    {
        "template_type": TemplateType.CONSENT_REQUEST,
        "name": "Digital Consent Request",
        "description": "Request for patient to complete digital consent",
        "channel": CommunicationChannel.EMAIL,
        "subject_template": "Consent required for {trial_name}",
        "content_template": (
            "Digital consent request for {trial_name}. "
            "Please review and sign."
        ),
    },
    {
        "template_type": TemplateType.ENROLLMENT_CONFIRMATION,
        "name": "Enrollment Confirmation",
        "description": "Confirmation of patient enrollment in a trial",
        "channel": CommunicationChannel.EMAIL,
        "subject_template": "Enrollment confirmed: {trial_name}",
        "content_template": (
            "Enrollment confirmation for {trial_name}. "
            "Welcome to the study."
        ),
    },
    {
        "template_type": TemplateType.FOLLOW_UP_REMINDER,
        "name": "Follow-up Visit Reminder",
        "description": "Reminder for a follow-up visit",
        "channel": CommunicationChannel.SMS,
        "subject_template": "Follow-up visit on {visit_date}",
        "content_template": (
            "Follow-up reminder for {visit_date} at {site_name}."
        ),
    },
    {
        "template_type": TemplateType.WITHDRAWAL_ACKNOWLEDGMENT,
        "name": "Withdrawal Confirmation",
        "description": "Acknowledgment of patient withdrawal from a trial",
        "channel": CommunicationChannel.EMAIL,
        "subject_template": "Withdrawal confirmed: {trial_name}",
        "content_template": (
            "Withdrawal acknowledgment for {trial_name}. "
            "Thank you for your participation."
        ),
    },
]


class PatientEngagementService:
    """In-memory patient engagement and communication tracking.

    Thread-safe via a reentrant lock. Tracks communications,
    engagement scoring, campaigns, patient preferences, and analytics.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # communication_id -> CommunicationRecord
        self._communications: dict[str, CommunicationRecord] = {}
        # template_id -> CommunicationTemplate
        self._templates: dict[str, CommunicationTemplate] = {}
        # campaign_id -> Campaign
        self._campaigns: dict[str, Campaign] = {}
        # patient_id -> PatientPreferences
        self._preferences: dict[str, PatientPreferences] = {}

        # Initialize default templates
        self._init_default_templates()

    # ------------------------------------------------------------------
    # Template initialization
    # ------------------------------------------------------------------

    def _init_default_templates(self) -> None:
        """Load default communication templates."""
        now = datetime.now(timezone.utc)
        for tmpl_data in _DEFAULT_TEMPLATES:
            tmpl_id = f"tmpl-{tmpl_data['template_type'].value.lower()}"
            template = CommunicationTemplate(
                id=tmpl_id,
                template_type=tmpl_data["template_type"],
                name=tmpl_data["name"],
                description=tmpl_data["description"],
                channel=tmpl_data["channel"],
                subject_template=tmpl_data["subject_template"],
                content_template=tmpl_data["content_template"],
                is_active=True,
                created_at=now,
            )
            self._templates[tmpl_id] = template

    # ------------------------------------------------------------------
    # Communication CRUD
    # ------------------------------------------------------------------

    def record_communication(
        self,
        request: CommunicationCreateRequest,
    ) -> CommunicationRecord:
        """Record a new communication.

        Args:
            request: Communication creation request.

        Returns:
            The created CommunicationRecord.
        """
        now = datetime.now(timezone.utc)
        comm_id = str(uuid.uuid4())

        record = CommunicationRecord(
            id=comm_id,
            patient_id=request.patient_id,
            trial_id=request.trial_id,
            channel=request.channel,
            direction=request.direction,
            subject=request.subject,
            content_summary=request.content_summary,
            status=CommunicationStatus.SENT,
            template_id=request.template_id,
            campaign_id=request.campaign_id,
            sent_at=now,
            created_at=now,
        )

        with self._lock:
            self._communications[comm_id] = record

            # Update campaign counters if applicable
            if request.campaign_id and request.campaign_id in self._campaigns:
                campaign = self._campaigns[request.campaign_id]
                self._campaigns[request.campaign_id] = campaign.model_copy(
                    update={"total_sent": campaign.total_sent + 1}
                )

        logger.info(
            "Communication recorded: id=%s patient=%s channel=%s",
            comm_id,
            request.patient_id,
            request.channel.value,
        )
        return record

    def get_communication(self, comm_id: str) -> CommunicationRecord | None:
        """Get a communication by ID.

        Args:
            comm_id: Communication identifier.

        Returns:
            The CommunicationRecord or None if not found.
        """
        with self._lock:
            return self._communications.get(comm_id)

    def list_communications(
        self,
        patient_id: str | None = None,
        trial_id: str | None = None,
        channel: CommunicationChannel | None = None,
        status: CommunicationStatus | None = None,
        campaign_id: str | None = None,
        direction: CommunicationDirection | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CommunicationListResponse:
        """List communications with optional filters.

        Args:
            patient_id: Filter by patient.
            trial_id: Filter by trial.
            channel: Filter by channel.
            status: Filter by status.
            campaign_id: Filter by campaign.
            direction: Filter by direction.
            limit: Maximum results to return.
            offset: Results offset.

        Returns:
            CommunicationListResponse with matching records.
        """
        with self._lock:
            records = list(self._communications.values())

        # Apply filters
        if patient_id:
            records = [r for r in records if r.patient_id == patient_id]
        if trial_id:
            records = [r for r in records if r.trial_id == trial_id]
        if channel:
            records = [r for r in records if r.channel == channel]
        if status:
            records = [r for r in records if r.status == status]
        if campaign_id:
            records = [r for r in records if r.campaign_id == campaign_id]
        if direction:
            records = [r for r in records if r.direction == direction]

        # Sort by created_at descending
        records.sort(key=lambda r: r.created_at, reverse=True)

        total = len(records)
        paginated = records[offset : offset + limit]

        return CommunicationListResponse(items=paginated, total=total)

    def update_communication_status(
        self,
        comm_id: str,
        request: CommunicationUpdateRequest,
    ) -> CommunicationRecord:
        """Update the status of a communication.

        Args:
            comm_id: Communication identifier.
            request: Status update request.

        Returns:
            The updated CommunicationRecord.

        Raises:
            ValueError: If communication not found.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            record = self._communications.get(comm_id)
            if record is None:
                raise ValueError(
                    f"Communication not found: {comm_id}"
                )

            update_fields: dict = {"status": request.status}

            if request.status == CommunicationStatus.DELIVERED:
                update_fields["delivered_at"] = now
            elif request.status == CommunicationStatus.OPENED:
                if record.delivered_at is None:
                    update_fields["delivered_at"] = now
                update_fields["opened_at"] = now
            elif request.status == CommunicationStatus.RESPONDED:
                if record.delivered_at is None:
                    update_fields["delivered_at"] = now
                if record.opened_at is None:
                    update_fields["opened_at"] = now
                update_fields["responded_at"] = now

            updated = record.model_copy(update=update_fields)
            self._communications[comm_id] = updated

            # Update campaign counters
            if updated.campaign_id and updated.campaign_id in self._campaigns:
                campaign = self._campaigns[updated.campaign_id]
                counter_updates: dict = {}
                if request.status == CommunicationStatus.DELIVERED:
                    counter_updates["total_delivered"] = (
                        campaign.total_delivered + 1
                    )
                elif request.status == CommunicationStatus.OPENED:
                    counter_updates["total_opened"] = (
                        campaign.total_opened + 1
                    )
                elif request.status == CommunicationStatus.RESPONDED:
                    counter_updates["total_responded"] = (
                        campaign.total_responded + 1
                    )
                if counter_updates:
                    self._campaigns[updated.campaign_id] = (
                        campaign.model_copy(update=counter_updates)
                    )

        logger.info(
            "Communication updated: id=%s status=%s",
            comm_id,
            request.status.value,
        )
        return updated

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def list_templates(
        self,
        template_type: TemplateType | None = None,
        channel: CommunicationChannel | None = None,
        active_only: bool = True,
    ) -> list[CommunicationTemplate]:
        """List communication templates.

        Args:
            template_type: Filter by template type.
            channel: Filter by default channel.
            active_only: Only return active templates.

        Returns:
            List of matching CommunicationTemplate objects.
        """
        with self._lock:
            templates = list(self._templates.values())

        if active_only:
            templates = [t for t in templates if t.is_active]
        if template_type:
            templates = [
                t for t in templates if t.template_type == template_type
            ]
        if channel:
            templates = [t for t in templates if t.channel == channel]

        return templates

    def get_template(self, template_id: str) -> CommunicationTemplate | None:
        """Get a template by ID."""
        with self._lock:
            return self._templates.get(template_id)

    # ------------------------------------------------------------------
    # Engagement scoring
    # ------------------------------------------------------------------

    def get_engagement_score(self, patient_id: str) -> EngagementScore:
        """Calculate the engagement score for a patient.

        Score components:
        - Response rate (responded / outbound sent) -- 40% weight
        - Response time (inverse of avg hours) -- 20% weight
        - Appointment adherence -- 20% weight
        - Channel preference satisfaction -- 20% weight

        Args:
            patient_id: Patient identifier.

        Returns:
            EngagementScore with breakdown.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            patient_comms = [
                c
                for c in self._communications.values()
                if c.patient_id == patient_id
            ]
            preferences = self._preferences.get(patient_id)

        # Outbound communications only for scoring
        outbound = [
            c
            for c in patient_comms
            if c.direction == CommunicationDirection.OUTBOUND
        ]

        total_sent = len(outbound)
        responded = [
            c for c in outbound if c.status == CommunicationStatus.RESPONDED
        ]
        total_responses = len(responded)

        # Response rate
        response_rate = (
            total_responses / total_sent if total_sent > 0 else 0.0
        )

        # Average response time
        response_times: list[float] = []
        for c in responded:
            if c.sent_at and c.responded_at:
                delta = (c.responded_at - c.sent_at).total_seconds() / 3600.0
                response_times.append(delta)
        avg_response_time = (
            sum(response_times) / len(response_times)
            if response_times
            else None
        )

        # Channel preference satisfaction
        preferred_channel = (
            preferences.preferred_channel
            if preferences
            else CommunicationChannel.EMAIL
        )
        preferred_count = sum(
            1 for c in outbound if c.channel == preferred_channel
        )
        channel_satisfaction = (
            preferred_count / total_sent if total_sent > 0 else 1.0
        )

        # Appointment adherence (default to 1.0 -- would need appointment
        # data integration for real tracking)
        appointment_adherence = 1.0

        # Calculate overall score (0-100)
        # Response rate: 40%, response time: 20%, adherence: 20%,
        # channel pref: 20%
        response_time_score = 1.0
        if avg_response_time is not None:
            # Score decreases as response time increases
            # 0 hours = 1.0, 24 hours = 0.5, 48+ hours = ~0.25
            response_time_score = 1.0 / (1.0 + avg_response_time / 24.0)

        overall = (
            response_rate * 40.0
            + response_time_score * 20.0
            + appointment_adherence * 20.0
            + channel_satisfaction * 20.0
        )

        return EngagementScore(
            patient_id=patient_id,
            overall_score=round(min(overall, 100.0), 2),
            response_rate=round(response_rate, 4),
            avg_response_time_hours=(
                round(avg_response_time, 2) if avg_response_time else None
            ),
            appointment_adherence=appointment_adherence,
            channel_preference_satisfaction=round(channel_satisfaction, 4),
            total_communications=total_sent,
            total_responses=total_responses,
            calculated_at=now,
        )

    # ------------------------------------------------------------------
    # Patient preferences
    # ------------------------------------------------------------------

    def get_preferences(self, patient_id: str) -> PatientPreferences:
        """Get communication preferences for a patient.

        Returns default preferences if none have been set.

        Args:
            patient_id: Patient identifier.

        Returns:
            PatientPreferences for the patient.
        """
        with self._lock:
            prefs = self._preferences.get(patient_id)
            if prefs is None:
                prefs = PatientPreferences(patient_id=patient_id)
            return prefs

    def update_preferences(
        self,
        patient_id: str,
        request: PreferencesUpdateRequest,
    ) -> PatientPreferences:
        """Update communication preferences for a patient.

        Args:
            patient_id: Patient identifier.
            request: Preference update request.

        Returns:
            The updated PatientPreferences.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self._preferences.get(
                patient_id,
                PatientPreferences(patient_id=patient_id),
            )

            update_fields: dict = {"updated_at": now}

            if request.preferred_channel is not None:
                update_fields["preferred_channel"] = request.preferred_channel
            if request.alternate_channel is not None:
                update_fields["alternate_channel"] = request.alternate_channel
            if request.frequency_limit is not None:
                update_fields["frequency_limit"] = request.frequency_limit
            if request.frequency_unit is not None:
                update_fields["frequency_unit"] = request.frequency_unit
            if request.opted_out is not None:
                update_fields["opted_out"] = request.opted_out
                if request.opted_out:
                    update_fields["opt_out_date"] = now
                else:
                    update_fields["opt_out_date"] = None
            if request.opt_out_reason is not None:
                update_fields["opt_out_reason"] = request.opt_out_reason
            if request.quiet_hours_start is not None:
                update_fields["quiet_hours_start"] = request.quiet_hours_start
            if request.quiet_hours_end is not None:
                update_fields["quiet_hours_end"] = request.quiet_hours_end

            updated = existing.model_copy(update=update_fields)
            self._preferences[patient_id] = updated

        logger.info(
            "Preferences updated: patient=%s",
            patient_id,
        )
        return updated

    # ------------------------------------------------------------------
    # Campaign management
    # ------------------------------------------------------------------

    def create_campaign(
        self,
        request: CampaignCreateRequest,
    ) -> Campaign:
        """Create a new communication campaign.

        Args:
            request: Campaign creation request.

        Returns:
            The created Campaign.
        """
        now = datetime.now(timezone.utc)
        campaign_id = str(uuid.uuid4())

        campaign = Campaign(
            id=campaign_id,
            name=request.name,
            trial_id=request.trial_id,
            template_id=request.template_id,
            target_criteria=request.target_criteria,
            schedule=request.schedule,
            status=CampaignStatus.DRAFT,
            created_at=now,
        )

        with self._lock:
            self._campaigns[campaign_id] = campaign

        logger.info(
            "Campaign created: id=%s name=%s",
            campaign_id,
            request.name,
        )
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        """Get a campaign by ID."""
        with self._lock:
            return self._campaigns.get(campaign_id)

    def list_campaigns(
        self,
        trial_id: str | None = None,
        status: CampaignStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CampaignListResponse:
        """List campaigns with optional filters.

        Args:
            trial_id: Filter by trial.
            status: Filter by status.
            limit: Maximum results.
            offset: Results offset.

        Returns:
            CampaignListResponse with matching campaigns.
        """
        with self._lock:
            campaigns = list(self._campaigns.values())

        if trial_id:
            campaigns = [c for c in campaigns if c.trial_id == trial_id]
        if status:
            campaigns = [c for c in campaigns if c.status == status]

        campaigns.sort(key=lambda c: c.created_at, reverse=True)
        total = len(campaigns)
        paginated = campaigns[offset : offset + limit]

        return CampaignListResponse(items=paginated, total=total)

    def update_campaign_status(
        self,
        campaign_id: str,
        new_status: CampaignStatus,
    ) -> Campaign:
        """Update campaign status.

        Args:
            campaign_id: Campaign identifier.
            new_status: New status.

        Returns:
            The updated Campaign.

        Raises:
            ValueError: If campaign not found.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                raise ValueError(f"Campaign not found: {campaign_id}")

            update_fields: dict = {"status": new_status}
            if new_status == CampaignStatus.ACTIVE:
                update_fields["started_at"] = now
            elif new_status in (
                CampaignStatus.COMPLETED,
                CampaignStatus.CANCELLED,
            ):
                update_fields["completed_at"] = now

            updated = campaign.model_copy(update=update_fields)
            self._campaigns[campaign_id] = updated

        logger.info(
            "Campaign status updated: id=%s status=%s",
            campaign_id,
            new_status.value,
        )
        return updated

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_analytics(
        self,
        trial_id: str | None = None,
    ) -> EngagementAnalytics:
        """Calculate comprehensive engagement analytics.

        Args:
            trial_id: Optional filter by trial.

        Returns:
            EngagementAnalytics with channel effectiveness, template
            performance, best send times, and engagement funnel.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            all_comms = list(self._communications.values())
            templates = dict(self._templates)

        # Filter by trial if specified
        if trial_id:
            all_comms = [c for c in all_comms if c.trial_id == trial_id]

        # Outbound only for most analytics
        outbound = [
            c
            for c in all_comms
            if c.direction == CommunicationDirection.OUTBOUND
        ]

        # -- Channel effectiveness --
        channel_stats: dict[CommunicationChannel, dict] = defaultdict(
            lambda: {
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "responded": 0,
            }
        )
        for c in outbound:
            stats = channel_stats[c.channel]
            stats["sent"] += 1
            if c.status in (
                CommunicationStatus.DELIVERED,
                CommunicationStatus.OPENED,
                CommunicationStatus.RESPONDED,
            ):
                stats["delivered"] += 1
            if c.status in (
                CommunicationStatus.OPENED,
                CommunicationStatus.RESPONDED,
            ):
                stats["opened"] += 1
            if c.status == CommunicationStatus.RESPONDED:
                stats["responded"] += 1

        channel_effectiveness = []
        for ch, stats in channel_stats.items():
            sent = stats["sent"]
            channel_effectiveness.append(
                ChannelEffectiveness(
                    channel=ch,
                    total_sent=sent,
                    total_delivered=stats["delivered"],
                    total_opened=stats["opened"],
                    total_responded=stats["responded"],
                    delivery_rate=(
                        stats["delivered"] / sent if sent > 0 else 0.0
                    ),
                    open_rate=(
                        stats["opened"] / stats["delivered"]
                        if stats["delivered"] > 0
                        else 0.0
                    ),
                    response_rate=(
                        stats["responded"] / sent if sent > 0 else 0.0
                    ),
                )
            )

        # -- Template performance --
        tmpl_stats: dict[str, dict] = defaultdict(
            lambda: {
                "sent": 0,
                "responded": 0,
                "response_times": [],
            }
        )
        for c in outbound:
            if c.template_id:
                ts = tmpl_stats[c.template_id]
                ts["sent"] += 1
                if c.status == CommunicationStatus.RESPONDED:
                    ts["responded"] += 1
                    if c.sent_at and c.responded_at:
                        delta_hours = (
                            (c.responded_at - c.sent_at).total_seconds()
                            / 3600.0
                        )
                        ts["response_times"].append(delta_hours)

        template_performance = []
        for tmpl_id, ts in tmpl_stats.items():
            tmpl = templates.get(tmpl_id)
            sent = ts["sent"]
            avg_rt = (
                sum(ts["response_times"]) / len(ts["response_times"])
                if ts["response_times"]
                else None
            )
            template_performance.append(
                TemplatePerformance(
                    template_id=tmpl_id,
                    template_type=(
                        tmpl.template_type
                        if tmpl
                        else TemplateType.SCREENING_INVITATION
                    ),
                    template_name=tmpl.name if tmpl else tmpl_id,
                    total_sent=sent,
                    total_responded=ts["responded"],
                    response_rate=(
                        ts["responded"] / sent if sent > 0 else 0.0
                    ),
                    avg_response_time_hours=(
                        round(avg_rt, 2) if avg_rt is not None else None
                    ),
                )
            )

        # -- Best send times (by hour of day) --
        hour_stats: dict[int, dict] = defaultdict(
            lambda: {"sent": 0, "responded": 0}
        )
        for c in outbound:
            if c.sent_at:
                hour = c.sent_at.hour
                hour_stats[hour]["sent"] += 1
                if c.status == CommunicationStatus.RESPONDED:
                    hour_stats[hour]["responded"] += 1

        best_send_times = []
        for hour in sorted(hour_stats.keys()):
            hs = hour_stats[hour]
            sent = hs["sent"]
            best_send_times.append(
                TimePeriodEffectiveness(
                    period=f"{hour:02d}:00",
                    total_sent=sent,
                    total_responded=hs["responded"],
                    response_rate=(
                        hs["responded"] / sent if sent > 0 else 0.0
                    ),
                )
            )

        # -- Engagement funnel --
        total_sent = len(outbound)
        total_delivered = sum(
            1
            for c in outbound
            if c.status
            in (
                CommunicationStatus.DELIVERED,
                CommunicationStatus.OPENED,
                CommunicationStatus.RESPONDED,
            )
        )
        total_opened = sum(
            1
            for c in outbound
            if c.status
            in (
                CommunicationStatus.OPENED,
                CommunicationStatus.RESPONDED,
            )
        )
        total_responded = sum(
            1
            for c in outbound
            if c.status == CommunicationStatus.RESPONDED
        )

        unique_patients = {c.patient_id for c in all_comms}

        funnel = EngagementFunnel(
            total_patients=len(unique_patients),
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_opened=total_opened,
            total_responded=total_responded,
            delivery_rate=(
                total_delivered / total_sent if total_sent > 0 else 0.0
            ),
            open_rate=(
                total_opened / total_delivered
                if total_delivered > 0
                else 0.0
            ),
            response_rate=(
                total_responded / total_sent if total_sent > 0 else 0.0
            ),
        )

        # -- Average engagement score --
        scores: list[float] = []
        for pid in unique_patients:
            score = self.get_engagement_score(pid)
            scores.append(score.overall_score)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return EngagementAnalytics(
            channel_effectiveness=channel_effectiveness,
            template_performance=template_performance,
            best_send_times=best_send_times,
            engagement_funnel=funnel,
            total_communications=len(all_comms),
            total_patients=len(unique_patients),
            avg_engagement_score=round(avg_score, 2),
            calculated_at=now,
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        with self._lock:
            return {
                "total_communications": len(self._communications),
                "total_templates": len(self._templates),
                "total_campaigns": len(self._campaigns),
                "total_patients_with_preferences": len(self._preferences),
            }


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_patient_engagement_service: PatientEngagementService | None = None


def get_patient_engagement_service() -> PatientEngagementService:
    """Get or create the singleton PatientEngagementService instance."""
    global _patient_engagement_service
    if _patient_engagement_service is None:
        _patient_engagement_service = PatientEngagementService()
    return _patient_engagement_service


def reset_patient_engagement_service() -> None:
    """Reset the singleton for testing."""
    global _patient_engagement_service
    _patient_engagement_service = None
