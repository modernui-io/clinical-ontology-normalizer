"""Tests for Patient Engagement and Communication Tracking (VP-Product-6).

Covers:
- Schema construction and enum validation
- PatientEngagementService CRUD operations
- Communication status lifecycle transitions
- Engagement scoring computation
- Patient preference management
- Campaign management
- Template listing and filtering
- Analytics computation
- API endpoint validation
- Edge cases and error handling

40+ test cases.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

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
from app.services.patient_engagement_service import (
    PatientEngagementService,
    get_patient_engagement_service,
    reset_patient_engagement_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> PatientEngagementService:
    """Create a fresh PatientEngagementService instance for each test."""
    return PatientEngagementService()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API endpoint tests."""
    reset_patient_engagement_service()
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _make_comm_request(**overrides) -> CommunicationCreateRequest:
    """Helper to build a CommunicationCreateRequest with defaults."""
    defaults = {
        "patient_id": "PAT-100",
        "trial_id": "TRIAL-001",
        "channel": CommunicationChannel.EMAIL,
        "direction": CommunicationDirection.OUTBOUND,
        "subject": "Trial Screening Invitation",
        "content_summary": "Screening invitation sent",
        "template_id": None,
        "campaign_id": None,
    }
    defaults.update(overrides)
    return CommunicationCreateRequest(**defaults)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemas:
    """Test Pydantic schema construction and validation."""

    def test_communication_channel_enum(self) -> None:
        """All communication channel values exist."""
        channels = [c.value for c in CommunicationChannel]
        assert "EMAIL" in channels
        assert "SMS" in channels
        assert "PHONE" in channels
        assert "IN_APP" in channels
        assert "PORTAL" in channels

    def test_communication_direction_enum(self) -> None:
        """All communication direction values exist."""
        directions = [d.value for d in CommunicationDirection]
        assert "INBOUND" in directions
        assert "OUTBOUND" in directions

    def test_communication_status_enum(self) -> None:
        """All communication status values exist."""
        statuses = [s.value for s in CommunicationStatus]
        assert "SENT" in statuses
        assert "DELIVERED" in statuses
        assert "OPENED" in statuses
        assert "RESPONDED" in statuses
        assert "FAILED" in statuses
        assert "BOUNCED" in statuses

    def test_template_type_enum(self) -> None:
        """All template type values exist."""
        types = [t.value for t in TemplateType]
        assert "SCREENING_INVITATION" in types
        assert "ELIGIBILITY_RESULT" in types
        assert "APPOINTMENT_REMINDER" in types
        assert "CONSENT_REQUEST" in types
        assert "ENROLLMENT_CONFIRMATION" in types
        assert "FOLLOW_UP_REMINDER" in types
        assert "WITHDRAWAL_ACKNOWLEDGMENT" in types

    def test_campaign_status_enum(self) -> None:
        """All campaign status values exist."""
        statuses = [s.value for s in CampaignStatus]
        assert "DRAFT" in statuses
        assert "SCHEDULED" in statuses
        assert "ACTIVE" in statuses
        assert "PAUSED" in statuses
        assert "COMPLETED" in statuses
        assert "CANCELLED" in statuses

    def test_communication_record_construction(self) -> None:
        """CommunicationRecord can be constructed with all fields."""
        now = datetime.now(timezone.utc)
        record = CommunicationRecord(
            id="comm-1",
            patient_id="PAT-100",
            trial_id="TRIAL-001",
            channel=CommunicationChannel.EMAIL,
            direction=CommunicationDirection.OUTBOUND,
            subject="Test subject",
            content_summary="Test summary",
            status=CommunicationStatus.SENT,
            template_id="tmpl-1",
            campaign_id="camp-1",
            sent_at=now,
            created_at=now,
        )
        assert record.id == "comm-1"
        assert record.patient_id == "PAT-100"
        assert record.channel == CommunicationChannel.EMAIL
        assert record.status == CommunicationStatus.SENT

    def test_engagement_score_bounds(self) -> None:
        """EngagementScore enforces 0-100 bounds on overall_score."""
        now = datetime.now(timezone.utc)
        score = EngagementScore(
            patient_id="PAT-100",
            overall_score=75.5,
            response_rate=0.5,
            appointment_adherence=1.0,
            channel_preference_satisfaction=1.0,
            calculated_at=now,
        )
        assert 0.0 <= score.overall_score <= 100.0

    def test_patient_preferences_defaults(self) -> None:
        """PatientPreferences has sensible defaults."""
        prefs = PatientPreferences(patient_id="PAT-100")
        assert prefs.preferred_channel == CommunicationChannel.EMAIL
        assert prefs.frequency_limit == 5
        assert prefs.frequency_unit == FrequencyUnit.WEEK
        assert prefs.opted_out is False

    def test_campaign_construction(self) -> None:
        """Campaign can be constructed with required fields."""
        now = datetime.now(timezone.utc)
        campaign = Campaign(
            id="camp-1",
            name="Test Campaign",
            trial_id="TRIAL-001",
            status=CampaignStatus.DRAFT,
            created_at=now,
        )
        assert campaign.id == "camp-1"
        assert campaign.status == CampaignStatus.DRAFT
        assert campaign.total_sent == 0

    def test_engagement_funnel_defaults(self) -> None:
        """EngagementFunnel has zero defaults."""
        funnel = EngagementFunnel()
        assert funnel.total_patients == 0
        assert funnel.total_sent == 0
        assert funnel.delivery_rate == 0.0


# ---------------------------------------------------------------------------
# Service: Communication CRUD tests
# ---------------------------------------------------------------------------


class TestCommunicationCRUD:
    """Test communication record CRUD operations."""

    def test_record_communication(self, service: PatientEngagementService) -> None:
        """Recording a communication returns a valid record."""
        req = _make_comm_request()
        record = service.record_communication(req)

        assert record.id is not None
        assert record.patient_id == "PAT-100"
        assert record.trial_id == "TRIAL-001"
        assert record.channel == CommunicationChannel.EMAIL
        assert record.direction == CommunicationDirection.OUTBOUND
        assert record.status == CommunicationStatus.SENT
        assert record.sent_at is not None

    def test_get_communication(self, service: PatientEngagementService) -> None:
        """Can retrieve a recorded communication by ID."""
        req = _make_comm_request()
        record = service.record_communication(req)

        fetched = service.get_communication(record.id)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.patient_id == record.patient_id

    def test_get_communication_not_found(
        self, service: PatientEngagementService
    ) -> None:
        """Getting a nonexistent communication returns None."""
        assert service.get_communication("nonexistent") is None

    def test_list_communications_empty(
        self, service: PatientEngagementService
    ) -> None:
        """Listing with no records returns empty list."""
        result = service.list_communications()
        assert result.total == 0
        assert result.items == []

    def test_list_communications_filter_by_patient(
        self, service: PatientEngagementService
    ) -> None:
        """Listing filters by patient_id correctly."""
        service.record_communication(
            _make_comm_request(patient_id="PAT-A")
        )
        service.record_communication(
            _make_comm_request(patient_id="PAT-B")
        )

        result = service.list_communications(patient_id="PAT-A")
        assert result.total == 1
        assert result.items[0].patient_id == "PAT-A"

    def test_list_communications_filter_by_channel(
        self, service: PatientEngagementService
    ) -> None:
        """Listing filters by channel correctly."""
        service.record_communication(
            _make_comm_request(channel=CommunicationChannel.EMAIL)
        )
        service.record_communication(
            _make_comm_request(channel=CommunicationChannel.SMS)
        )

        result = service.list_communications(
            channel=CommunicationChannel.SMS
        )
        assert result.total == 1
        assert result.items[0].channel == CommunicationChannel.SMS

    def test_list_communications_filter_by_direction(
        self, service: PatientEngagementService
    ) -> None:
        """Listing filters by direction correctly."""
        service.record_communication(
            _make_comm_request(direction=CommunicationDirection.OUTBOUND)
        )
        service.record_communication(
            _make_comm_request(direction=CommunicationDirection.INBOUND)
        )

        result = service.list_communications(
            direction=CommunicationDirection.INBOUND
        )
        assert result.total == 1
        assert (
            result.items[0].direction == CommunicationDirection.INBOUND
        )

    def test_list_communications_pagination(
        self, service: PatientEngagementService
    ) -> None:
        """Listing respects limit and offset."""
        for i in range(5):
            service.record_communication(
                _make_comm_request(patient_id=f"PAT-{i}")
            )

        result = service.list_communications(limit=2, offset=0)
        assert len(result.items) == 2
        assert result.total == 5

        result2 = service.list_communications(limit=2, offset=3)
        assert len(result2.items) == 2
        assert result2.total == 5

    def test_update_communication_status_delivered(
        self, service: PatientEngagementService
    ) -> None:
        """Updating to DELIVERED sets delivered_at timestamp."""
        record = service.record_communication(_make_comm_request())
        updated = service.update_communication_status(
            record.id,
            CommunicationUpdateRequest(status=CommunicationStatus.DELIVERED),
        )
        assert updated.status == CommunicationStatus.DELIVERED
        assert updated.delivered_at is not None

    def test_update_communication_status_opened(
        self, service: PatientEngagementService
    ) -> None:
        """Updating to OPENED sets opened_at and delivered_at."""
        record = service.record_communication(_make_comm_request())
        updated = service.update_communication_status(
            record.id,
            CommunicationUpdateRequest(status=CommunicationStatus.OPENED),
        )
        assert updated.status == CommunicationStatus.OPENED
        assert updated.opened_at is not None
        assert updated.delivered_at is not None

    def test_update_communication_status_responded(
        self, service: PatientEngagementService
    ) -> None:
        """Updating to RESPONDED sets responded_at, opened_at, delivered_at."""
        record = service.record_communication(_make_comm_request())
        updated = service.update_communication_status(
            record.id,
            CommunicationUpdateRequest(status=CommunicationStatus.RESPONDED),
        )
        assert updated.status == CommunicationStatus.RESPONDED
        assert updated.responded_at is not None
        assert updated.opened_at is not None
        assert updated.delivered_at is not None

    def test_update_communication_not_found(
        self, service: PatientEngagementService
    ) -> None:
        """Updating a nonexistent communication raises ValueError."""
        with pytest.raises(ValueError, match="Communication not found"):
            service.update_communication_status(
                "nonexistent",
                CommunicationUpdateRequest(
                    status=CommunicationStatus.DELIVERED
                ),
            )

    def test_list_communications_filter_by_status(
        self, service: PatientEngagementService
    ) -> None:
        """Listing filters by communication status correctly."""
        r1 = service.record_communication(_make_comm_request())
        r2 = service.record_communication(_make_comm_request())
        service.update_communication_status(
            r1.id,
            CommunicationUpdateRequest(status=CommunicationStatus.DELIVERED),
        )

        result = service.list_communications(
            status=CommunicationStatus.DELIVERED
        )
        assert result.total == 1
        assert result.items[0].id == r1.id

    def test_list_communications_filter_by_trial(
        self, service: PatientEngagementService
    ) -> None:
        """Listing filters by trial_id correctly."""
        service.record_communication(
            _make_comm_request(trial_id="TRIAL-A")
        )
        service.record_communication(
            _make_comm_request(trial_id="TRIAL-B")
        )

        result = service.list_communications(trial_id="TRIAL-A")
        assert result.total == 1


# ---------------------------------------------------------------------------
# Service: Template tests
# ---------------------------------------------------------------------------


class TestTemplates:
    """Test communication template operations."""

    def test_default_templates_loaded(
        self, service: PatientEngagementService
    ) -> None:
        """Service loads 7 default templates on init."""
        templates = service.list_templates()
        assert len(templates) == 7

    def test_template_types_covered(
        self, service: PatientEngagementService
    ) -> None:
        """All 7 TemplateType values have a default template."""
        templates = service.list_templates()
        types = {t.template_type for t in templates}
        for tt in TemplateType:
            assert tt in types, f"Missing template for {tt.value}"

    def test_filter_templates_by_type(
        self, service: PatientEngagementService
    ) -> None:
        """Templates can be filtered by template_type."""
        templates = service.list_templates(
            template_type=TemplateType.SCREENING_INVITATION
        )
        assert len(templates) == 1
        assert (
            templates[0].template_type
            == TemplateType.SCREENING_INVITATION
        )

    def test_filter_templates_by_channel(
        self, service: PatientEngagementService
    ) -> None:
        """Templates can be filtered by channel."""
        sms_templates = service.list_templates(
            channel=CommunicationChannel.SMS
        )
        for t in sms_templates:
            assert t.channel == CommunicationChannel.SMS

    def test_get_template_by_id(
        self, service: PatientEngagementService
    ) -> None:
        """Can retrieve a template by its ID."""
        tmpl = service.get_template("tmpl-screening_invitation")
        assert tmpl is not None
        assert tmpl.template_type == TemplateType.SCREENING_INVITATION

    def test_get_template_not_found(
        self, service: PatientEngagementService
    ) -> None:
        """Getting a nonexistent template returns None."""
        assert service.get_template("nonexistent") is None


# ---------------------------------------------------------------------------
# Service: Engagement scoring
# ---------------------------------------------------------------------------


class TestEngagementScoring:
    """Test engagement score computation."""

    def test_score_no_communications(
        self, service: PatientEngagementService
    ) -> None:
        """Patient with no communications gets a baseline score."""
        score = service.get_engagement_score("PAT-NEW")
        assert score.patient_id == "PAT-NEW"
        assert score.total_communications == 0
        assert score.total_responses == 0
        assert score.response_rate == 0.0

    def test_score_with_all_responded(
        self, service: PatientEngagementService
    ) -> None:
        """Patient who responds to all gets high response rate."""
        for _ in range(3):
            r = service.record_communication(
                _make_comm_request(patient_id="PAT-RESP")
            )
            service.update_communication_status(
                r.id,
                CommunicationUpdateRequest(
                    status=CommunicationStatus.RESPONDED
                ),
            )

        score = service.get_engagement_score("PAT-RESP")
        assert score.response_rate == 1.0
        assert score.total_communications == 3
        assert score.total_responses == 3
        assert score.overall_score > 50.0

    def test_score_with_no_responses(
        self, service: PatientEngagementService
    ) -> None:
        """Patient with no responses gets low response rate."""
        for _ in range(3):
            service.record_communication(
                _make_comm_request(patient_id="PAT-NORESP")
            )

        score = service.get_engagement_score("PAT-NORESP")
        assert score.response_rate == 0.0
        assert score.total_communications == 3
        assert score.total_responses == 0

    def test_score_channel_preference_satisfaction(
        self, service: PatientEngagementService
    ) -> None:
        """Channel satisfaction reflects preferred channel usage."""
        service.update_preferences(
            "PAT-PREF",
            PreferencesUpdateRequest(
                preferred_channel=CommunicationChannel.SMS
            ),
        )

        # Send via SMS (preferred)
        service.record_communication(
            _make_comm_request(
                patient_id="PAT-PREF",
                channel=CommunicationChannel.SMS,
            )
        )
        # Send via EMAIL (not preferred)
        service.record_communication(
            _make_comm_request(
                patient_id="PAT-PREF",
                channel=CommunicationChannel.EMAIL,
            )
        )

        score = service.get_engagement_score("PAT-PREF")
        assert score.channel_preference_satisfaction == 0.5

    def test_score_inbound_excluded(
        self, service: PatientEngagementService
    ) -> None:
        """Inbound communications are excluded from scoring."""
        service.record_communication(
            _make_comm_request(
                patient_id="PAT-IN",
                direction=CommunicationDirection.INBOUND,
            )
        )

        score = service.get_engagement_score("PAT-IN")
        assert score.total_communications == 0


# ---------------------------------------------------------------------------
# Service: Patient preferences
# ---------------------------------------------------------------------------


class TestPatientPreferences:
    """Test patient preference management."""

    def test_default_preferences(
        self, service: PatientEngagementService
    ) -> None:
        """Getting prefs for new patient returns defaults."""
        prefs = service.get_preferences("PAT-NEW")
        assert prefs.patient_id == "PAT-NEW"
        assert prefs.preferred_channel == CommunicationChannel.EMAIL
        assert prefs.opted_out is False

    def test_update_preferred_channel(
        self, service: PatientEngagementService
    ) -> None:
        """Updating preferred channel persists."""
        updated = service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(
                preferred_channel=CommunicationChannel.SMS
            ),
        )
        assert updated.preferred_channel == CommunicationChannel.SMS
        assert updated.updated_at is not None

        fetched = service.get_preferences("PAT-100")
        assert fetched.preferred_channel == CommunicationChannel.SMS

    def test_update_frequency_limit(
        self, service: PatientEngagementService
    ) -> None:
        """Updating frequency limit and unit persists."""
        updated = service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(
                frequency_limit=3,
                frequency_unit=FrequencyUnit.DAY,
            ),
        )
        assert updated.frequency_limit == 3
        assert updated.frequency_unit == FrequencyUnit.DAY

    def test_opt_out(self, service: PatientEngagementService) -> None:
        """Opting out sets opt_out_date."""
        updated = service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(
                opted_out=True,
                opt_out_reason="No longer interested",
            ),
        )
        assert updated.opted_out is True
        assert updated.opt_out_date is not None
        assert updated.opt_out_reason == "No longer interested"

    def test_opt_back_in(self, service: PatientEngagementService) -> None:
        """Opting back in clears opt_out_date."""
        service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(opted_out=True),
        )
        updated = service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(opted_out=False),
        )
        assert updated.opted_out is False
        assert updated.opt_out_date is None

    def test_quiet_hours(self, service: PatientEngagementService) -> None:
        """Setting quiet hours persists."""
        updated = service.update_preferences(
            "PAT-100",
            PreferencesUpdateRequest(
                quiet_hours_start=22,
                quiet_hours_end=8,
            ),
        )
        assert updated.quiet_hours_start == 22
        assert updated.quiet_hours_end == 8


# ---------------------------------------------------------------------------
# Service: Campaign management
# ---------------------------------------------------------------------------


class TestCampaignManagement:
    """Test campaign CRUD and status management."""

    def test_create_campaign(
        self, service: PatientEngagementService
    ) -> None:
        """Creating a campaign returns a valid record."""
        campaign = service.create_campaign(
            CampaignCreateRequest(
                name="Screening Outreach",
                trial_id="TRIAL-001",
                template_id="tmpl-screening_invitation",
                target_criteria={"status": "eligible"},
            )
        )
        assert campaign.id is not None
        assert campaign.name == "Screening Outreach"
        assert campaign.status == CampaignStatus.DRAFT
        assert campaign.total_sent == 0

    def test_get_campaign(
        self, service: PatientEngagementService
    ) -> None:
        """Can retrieve a campaign by ID."""
        created = service.create_campaign(
            CampaignCreateRequest(name="Test Campaign")
        )
        fetched = service.get_campaign(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_list_campaigns_empty(
        self, service: PatientEngagementService
    ) -> None:
        """Listing with no campaigns returns empty list."""
        result = service.list_campaigns()
        assert result.total == 0

    def test_list_campaigns_filter_by_trial(
        self, service: PatientEngagementService
    ) -> None:
        """Campaigns can be filtered by trial_id."""
        service.create_campaign(
            CampaignCreateRequest(name="A", trial_id="TRIAL-A")
        )
        service.create_campaign(
            CampaignCreateRequest(name="B", trial_id="TRIAL-B")
        )

        result = service.list_campaigns(trial_id="TRIAL-A")
        assert result.total == 1
        assert result.items[0].trial_id == "TRIAL-A"

    def test_update_campaign_status_active(
        self, service: PatientEngagementService
    ) -> None:
        """Activating a campaign sets started_at."""
        campaign = service.create_campaign(
            CampaignCreateRequest(name="Test")
        )
        updated = service.update_campaign_status(
            campaign.id, CampaignStatus.ACTIVE
        )
        assert updated.status == CampaignStatus.ACTIVE
        assert updated.started_at is not None

    def test_update_campaign_status_completed(
        self, service: PatientEngagementService
    ) -> None:
        """Completing a campaign sets completed_at."""
        campaign = service.create_campaign(
            CampaignCreateRequest(name="Test")
        )
        updated = service.update_campaign_status(
            campaign.id, CampaignStatus.COMPLETED
        )
        assert updated.status == CampaignStatus.COMPLETED
        assert updated.completed_at is not None

    def test_update_campaign_not_found(
        self, service: PatientEngagementService
    ) -> None:
        """Updating nonexistent campaign raises ValueError."""
        with pytest.raises(ValueError, match="Campaign not found"):
            service.update_campaign_status(
                "nonexistent", CampaignStatus.ACTIVE
            )

    def test_campaign_counters_update(
        self, service: PatientEngagementService
    ) -> None:
        """Campaign counters update when communications are recorded/updated."""
        campaign = service.create_campaign(
            CampaignCreateRequest(name="Counter Test")
        )

        r = service.record_communication(
            _make_comm_request(campaign_id=campaign.id)
        )

        updated_campaign = service.get_campaign(campaign.id)
        assert updated_campaign.total_sent == 1

        service.update_communication_status(
            r.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.DELIVERED
            ),
        )
        updated_campaign = service.get_campaign(campaign.id)
        assert updated_campaign.total_delivered == 1

        service.update_communication_status(
            r.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.RESPONDED
            ),
        )
        updated_campaign = service.get_campaign(campaign.id)
        assert updated_campaign.total_responded == 1


# ---------------------------------------------------------------------------
# Service: Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    """Test analytics computation."""

    def test_analytics_empty(
        self, service: PatientEngagementService
    ) -> None:
        """Analytics with no data returns zeros."""
        analytics = service.get_analytics()
        assert analytics.total_communications == 0
        assert analytics.total_patients == 0
        assert analytics.avg_engagement_score == 0.0

    def test_analytics_channel_effectiveness(
        self, service: PatientEngagementService
    ) -> None:
        """Analytics computes channel effectiveness."""
        # Send 2 emails, 1 responded
        r1 = service.record_communication(
            _make_comm_request(channel=CommunicationChannel.EMAIL)
        )
        service.update_communication_status(
            r1.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.RESPONDED
            ),
        )
        service.record_communication(
            _make_comm_request(channel=CommunicationChannel.EMAIL)
        )

        analytics = service.get_analytics()
        email_eff = [
            e
            for e in analytics.channel_effectiveness
            if e.channel == CommunicationChannel.EMAIL
        ]
        assert len(email_eff) == 1
        assert email_eff[0].total_sent == 2
        assert email_eff[0].total_responded == 1
        assert email_eff[0].response_rate == 0.5

    def test_analytics_engagement_funnel(
        self, service: PatientEngagementService
    ) -> None:
        """Analytics computes engagement funnel metrics."""
        r1 = service.record_communication(_make_comm_request())
        r2 = service.record_communication(_make_comm_request())
        service.update_communication_status(
            r1.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.DELIVERED
            ),
        )
        service.update_communication_status(
            r2.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.RESPONDED
            ),
        )

        analytics = service.get_analytics()
        funnel = analytics.engagement_funnel
        assert funnel.total_sent == 2
        assert funnel.total_delivered == 2  # responded implies delivered
        assert funnel.total_responded == 1

    def test_analytics_filter_by_trial(
        self, service: PatientEngagementService
    ) -> None:
        """Analytics can be filtered by trial_id."""
        service.record_communication(
            _make_comm_request(trial_id="TRIAL-A")
        )
        service.record_communication(
            _make_comm_request(trial_id="TRIAL-B")
        )

        analytics = service.get_analytics(trial_id="TRIAL-A")
        assert analytics.total_communications == 1

    def test_analytics_template_performance(
        self, service: PatientEngagementService
    ) -> None:
        """Analytics computes template performance metrics."""
        tmpl_id = "tmpl-screening_invitation"
        r1 = service.record_communication(
            _make_comm_request(template_id=tmpl_id)
        )
        service.update_communication_status(
            r1.id,
            CommunicationUpdateRequest(
                status=CommunicationStatus.RESPONDED
            ),
        )
        service.record_communication(
            _make_comm_request(template_id=tmpl_id)
        )

        analytics = service.get_analytics()
        tmpl_perf = [
            t
            for t in analytics.template_performance
            if t.template_id == tmpl_id
        ]
        assert len(tmpl_perf) == 1
        assert tmpl_perf[0].total_sent == 2
        assert tmpl_perf[0].total_responded == 1


# ---------------------------------------------------------------------------
# Service: Stats
# ---------------------------------------------------------------------------


class TestStats:
    """Test service statistics."""

    def test_get_stats(self, service: PatientEngagementService) -> None:
        """Stats reflect current service state."""
        stats = service.get_stats()
        assert stats["total_communications"] == 0
        assert stats["total_templates"] == 7
        assert stats["total_campaigns"] == 0

        service.record_communication(_make_comm_request())
        stats = service.get_stats()
        assert stats["total_communications"] == 1


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestAPIEndpoints:
    """Test API endpoints via TestClient."""

    def test_record_communication_endpoint(self, client: TestClient) -> None:
        """POST /engagement/communications creates a record."""
        resp = client.post(
            "/api/v1/engagement/communications",
            json={
                "patient_id": "PAT-API",
                "trial_id": "TRIAL-API",
                "channel": "EMAIL",
                "direction": "OUTBOUND",
                "subject": "API Test",
                "content_summary": "Test via API",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-API"
        assert data["status"] == "SENT"

    def test_list_communications_endpoint(self, client: TestClient) -> None:
        """GET /engagement/communications returns a list."""
        client.post(
            "/api/v1/engagement/communications",
            json={
                "patient_id": "PAT-LIST",
                "channel": "EMAIL",
                "direction": "OUTBOUND",
            },
        )
        resp = client.get(
            "/api/v1/engagement/communications",
            params={"patient_id": "PAT-LIST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_get_communication_endpoint(self, client: TestClient) -> None:
        """GET /engagement/communications/{id} returns a record."""
        create_resp = client.post(
            "/api/v1/engagement/communications",
            json={
                "patient_id": "PAT-GET",
                "channel": "SMS",
                "direction": "OUTBOUND",
            },
        )
        comm_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/v1/engagement/communications/{comm_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == comm_id

    def test_get_communication_not_found_endpoint(
        self, client: TestClient
    ) -> None:
        """GET /engagement/communications/{id} returns 404 for unknown."""
        resp = client.get(
            "/api/v1/engagement/communications/nonexistent"
        )
        assert resp.status_code == 404

    def test_update_communication_endpoint(self, client: TestClient) -> None:
        """PUT /engagement/communications/{id} updates status."""
        create_resp = client.post(
            "/api/v1/engagement/communications",
            json={
                "patient_id": "PAT-UPD",
                "channel": "EMAIL",
                "direction": "OUTBOUND",
            },
        )
        comm_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/engagement/communications/{comm_id}",
            json={"status": "DELIVERED"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DELIVERED"

    def test_update_communication_not_found_endpoint(
        self, client: TestClient
    ) -> None:
        """PUT /engagement/communications/{id} returns 404 for unknown."""
        resp = client.put(
            "/api/v1/engagement/communications/nonexistent",
            json={"status": "DELIVERED"},
        )
        assert resp.status_code == 404

    def test_list_templates_endpoint(self, client: TestClient) -> None:
        """GET /engagement/templates returns templates."""
        resp = client.get("/api/v1/engagement/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7

    def test_get_engagement_score_endpoint(
        self, client: TestClient
    ) -> None:
        """GET /engagement/patients/{id}/score returns a score."""
        resp = client.get(
            "/api/v1/engagement/patients/PAT-SCORE/score"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-SCORE"
        assert "overall_score" in data

    def test_get_preferences_endpoint(self, client: TestClient) -> None:
        """GET /engagement/patients/{id}/preferences returns prefs."""
        resp = client.get(
            "/api/v1/engagement/patients/PAT-PREFS/preferences"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-PREFS"
        assert data["preferred_channel"] == "EMAIL"

    def test_update_preferences_endpoint(self, client: TestClient) -> None:
        """PUT /engagement/patients/{id}/preferences updates prefs."""
        resp = client.put(
            "/api/v1/engagement/patients/PAT-PREFS/preferences",
            json={"preferred_channel": "SMS", "frequency_limit": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preferred_channel"] == "SMS"
        assert data["frequency_limit"] == 3

    def test_get_analytics_endpoint(self, client: TestClient) -> None:
        """GET /engagement/analytics returns analytics."""
        resp = client.get("/api/v1/engagement/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "channel_effectiveness" in data
        assert "engagement_funnel" in data
        assert "total_communications" in data

    def test_create_campaign_endpoint(self, client: TestClient) -> None:
        """POST /engagement/campaigns creates a campaign."""
        resp = client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": "API Campaign",
                "trial_id": "TRIAL-API",
                "template_id": "tmpl-screening_invitation",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Campaign"
        assert data["status"] == "DRAFT"

    def test_list_campaigns_endpoint(self, client: TestClient) -> None:
        """GET /engagement/campaigns returns campaigns."""
        client.post(
            "/api/v1/engagement/campaigns",
            json={"name": "List Test"},
        )
        resp = client.get("/api/v1/engagement/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test singleton pattern."""

    def test_singleton_returns_same_instance(self) -> None:
        """get_patient_engagement_service returns same instance."""
        reset_patient_engagement_service()
        s1 = get_patient_engagement_service()
        s2 = get_patient_engagement_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self) -> None:
        """reset_patient_engagement_service clears singleton."""
        s1 = get_patient_engagement_service()
        reset_patient_engagement_service()
        s2 = get_patient_engagement_service()
        assert s1 is not s2
