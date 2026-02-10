"""Tests for Medical Monitor Dashboard.

Covers:
- Seed data verification (signals, assessments, queries, case reviews, trends, notes)
- Safety signal CRUD, filtering, and escalation workflow
- Benefit-risk assessment creation, retrieval, and updates
- Medical query lifecycle (raise -> assign -> respond -> resolve)
- Patient case review workflow (create -> in_review -> complete)
- Safety trend analysis
- Medical monitor notes
- Metrics aggregation
- Error cases (404s, invalid transitions)
- Edge cases and enumeration coverage
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_monitor import (
    AssessmentOutcome,
    CaseReviewStatus,
    NoteCategory,
    NoteVisibility,
    QueryCategory,
    QueryStatus,
    ReviewPriority,
    RiskLevel,
    SignalStatus,
    TrendDirection,
)
from app.services.medical_monitor_service import (
    MedicalMonitorService,
    get_medical_monitor_service,
    reset_medical_monitor_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-monitor"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_monitor_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalMonitorService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "signal_name": "Test signal",
        "signal_type": "AE cluster",
        "detected_date": now.isoformat(),
        "source": "Automated detection",
        "description": "A test safety signal for unit testing",
        "affected_patients_count": 5,
        "incidence_rate": 3.0,
        "expected_rate": 1.0,
        "risk_level": "high",
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "assessor": "Dr. Test Assessor",
        "overall_outcome": "favorable",
        "benefit_score": 75.0,
        "risk_score": 25.0,
        "benefit_summary": "Strong efficacy signal observed",
        "risk_summary": "Manageable safety profile",
        "data_cutoff_date": now.isoformat(),
        "enrollment_at_assessment": 200,
    }
    defaults.update(overrides)
    return defaults


def _make_query_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "category": "safety",
        "subject": "Test medical query",
        "query_text": "This is a test medical query for unit testing",
        "raised_by": "Test Investigator",
    }
    defaults.update(overrides)
    return defaults


def _make_case_review_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "patient_id": "PAT-TEST-001",
        "review_reason": "Test case review",
        "priority": "routine",
    }
    defaults.update(overrides)
    return defaults


def _make_note_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "author": "Dr. Test Author",
        "category": "general",
        "subject": "Test note",
        "content": "This is a test note for unit testing",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_signals_count(self, svc: MedicalMonitorService):
        signals = svc.list_signals()
        assert len(signals) == 4

    def test_seed_assessments_count(self, svc: MedicalMonitorService):
        assessments = svc.list_assessments()
        assert len(assessments) == 3

    def test_seed_queries_count(self, svc: MedicalMonitorService):
        queries = svc.list_queries()
        assert len(queries) == 6

    def test_seed_case_reviews_count(self, svc: MedicalMonitorService):
        reviews = svc.list_case_reviews()
        assert len(reviews) == 4

    def test_seed_trends_count(self, svc: MedicalMonitorService):
        trends = svc.list_trends()
        assert len(trends) == 5

    def test_seed_notes_count(self, svc: MedicalMonitorService):
        notes = svc.list_notes()
        assert len(notes) == 3

    def test_seed_signal_statuses(self, svc: MedicalMonitorService):
        signals = svc.list_signals()
        statuses = {s.status for s in signals}
        assert SignalStatus.UNDER_REVIEW in statuses
        assert SignalStatus.CONFIRMED in statuses
        assert SignalStatus.ESCALATED in statuses
        assert SignalStatus.REFUTED in statuses

    def test_seed_signal_risk_levels(self, svc: MedicalMonitorService):
        signals = svc.list_signals()
        levels = {s.risk_level for s in signals}
        assert RiskLevel.LOW in levels
        assert RiskLevel.MODERATE in levels
        assert RiskLevel.HIGH in levels
        assert RiskLevel.VERY_HIGH in levels

    def test_seed_query_categories(self, svc: MedicalMonitorService):
        queries = svc.list_queries()
        categories = {q.category for q in queries}
        assert QueryCategory.SAFETY in categories
        assert QueryCategory.ELIGIBILITY in categories
        assert QueryCategory.PROTOCOL_COMPLIANCE in categories
        assert QueryCategory.DATA_CLARIFICATION in categories
        assert QueryCategory.EFFICACY in categories


# =====================================================================
# SAFETY SIGNAL CRUD
# =====================================================================


class TestSafetySignalCrud:
    """Test safety signal CRUD operations."""

    @pytest.mark.anyio
    async def test_list_signals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_signals_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_signals_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"status": "escalated"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "escalated"

    @pytest.mark.anyio
    async def test_list_signals_filter_risk_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals", params={"risk_level": "very_high"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_level"] == "very_high"

    @pytest.mark.anyio
    async def test_get_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-001"
        assert data["signal_name"] == "Elevated hepatotoxicity cluster"

    @pytest.mark.anyio
    async def test_get_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_signal(self, client: AsyncClient):
        payload = _make_signal_create()
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_name"] == "Test signal"
        assert data["status"] == "detected"
        assert data["id"].startswith("SIG-")

    @pytest.mark.anyio
    async def test_update_signal(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-001",
            json={"risk_level": "very_high", "assessment_notes": "Updated assessment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "very_high"
        assert data["assessment_notes"] == "Updated assessment"

    @pytest.mark.anyio
    async def test_update_signal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/signals/SIG-NONEXISTENT",
            json={"risk_level": "high"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_signal_status_sets_reviewed_date(self, client: AsyncClient):
        # Create a new signal (no reviewed_date)
        create_resp = await client.post(
            f"{API_PREFIX}/signals",
            json=_make_signal_create(),
        )
        signal_id = create_resp.json()["id"]
        assert create_resp.json()["reviewed_date"] is None

        # Update status to under_review
        resp = await client.put(
            f"{API_PREFIX}/signals/{signal_id}",
            json={"status": "under_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["reviewed_date"] is not None


# =====================================================================
# SAFETY SIGNAL ESCALATION
# =====================================================================


class TestSignalEscalation:
    """Test safety signal escalation workflow."""

    @pytest.mark.anyio
    async def test_escalate_signal(self, client: AsyncClient):
        payload = {
            "reason": "Disproportionality confirmed after detailed review",
            "escalated_to": "Safety Monitoring Committee",
            "recommended_action": "Consider protocol amendment",
        }
        resp = await client.post(f"{API_PREFIX}/signals/SIG-001/escalate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalated"
        assert "Safety Monitoring Committee" in data["assessment_notes"]

    @pytest.mark.anyio
    async def test_escalate_signal_not_found(self, client: AsyncClient):
        payload = {
            "reason": "Test",
            "escalated_to": "Test Committee",
        }
        resp = await client.post(f"{API_PREFIX}/signals/SIG-NONEXISTENT/escalate", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_escalate_closed_signal_fails(self, client: AsyncClient):
        # SIG-004 is refuted
        payload = {
            "reason": "Test",
            "escalated_to": "Test Committee",
        }
        resp = await client.post(f"{API_PREFIX}/signals/SIG-004/escalate", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_escalate_without_recommended_action(self, client: AsyncClient):
        payload = {
            "reason": "Urgent escalation needed",
            "escalated_to": "DSMB",
        }
        resp = await client.post(f"{API_PREFIX}/signals/SIG-002/escalate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalated"


# =====================================================================
# BENEFIT-RISK ASSESSMENTS
# =====================================================================


class TestBenefitRiskAssessments:
    """Test benefit-risk assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefit-risk-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/benefit-risk-assessments",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/benefit-risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessor"] == "Dr. Test Assessor"
        assert data["overall_outcome"] == "favorable"
        assert data["id"].startswith("BRA-")

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BRA-001"
        assert data["overall_outcome"] == "favorable"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-003",
            json={
                "overall_outcome": "unfavorable",
                "recommendations": "Recommend discontinuation of 480mg cohort",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_outcome"] == "unfavorable"
        assert "discontinuation" in data["recommendations"]

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-NONEXISTENT",
            json={"benefit_score": 50.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assessment_scores_valid_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefit-risk-assessments")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["benefit_score"] <= 100
            assert 0 <= item["risk_score"] <= 100

    @pytest.mark.anyio
    async def test_create_assessment_with_supporting_data(self, client: AsyncClient):
        payload = _make_assessment_create(
            supporting_data={"dsmb_recommendation": "continue", "interim_number": 3}
        )
        resp = await client.post(f"{API_PREFIX}/benefit-risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["supporting_data"]["dsmb_recommendation"] == "continue"


# =====================================================================
# MEDICAL QUERY LIFECYCLE
# =====================================================================


class TestMedicalQueryLifecycle:
    """Test medical query lifecycle: raise -> assign -> respond -> resolve."""

    @pytest.mark.anyio
    async def test_list_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_queries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_queries_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_queries_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"category": "safety"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "safety"

    @pytest.mark.anyio
    async def test_list_queries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "resolved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "resolved"

    @pytest.mark.anyio
    async def test_list_queries_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_create_query(self, client: AsyncClient):
        payload = _make_query_create()
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test medical query"
        assert data["status"] == "open"
        assert data["id"].startswith("MQ-")

    @pytest.mark.anyio
    async def test_get_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/MQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MQ-001"
        assert data["category"] == "safety"

    @pytest.mark.anyio
    async def test_get_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/MQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_query(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/MQ-005",
            json={"assigned_to": "Dr. Rachel Kim", "status": "assigned"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to"] == "Dr. Rachel Kim"
        assert data["status"] == "assigned"

    @pytest.mark.anyio
    async def test_update_query_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/MQ-NONEXISTENT",
            json={"priority": "critical"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_respond_to_query(self, client: AsyncClient):
        payload = {
            "response_text": "Use central lab values for efficacy analysis per protocol section 7.2.",
            "follow_up_required": False,
        }
        resp = await client.post(f"{API_PREFIX}/queries/MQ-005/respond", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "responded"
        assert data["response_text"] is not None
        assert data["responded_date"] is not None

    @pytest.mark.anyio
    async def test_respond_to_query_not_found(self, client: AsyncClient):
        payload = {"response_text": "Test response"}
        resp = await client.post(f"{API_PREFIX}/queries/MQ-NONEXISTENT/respond", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_respond_to_resolved_query_fails(self, client: AsyncClient):
        # MQ-001 is resolved
        payload = {"response_text": "Test"}
        resp = await client.post(f"{API_PREFIX}/queries/MQ-001/respond", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_full_query_lifecycle(self, client: AsyncClient):
        # Step 1: Create query
        create_resp = await client.post(
            f"{API_PREFIX}/queries",
            json=_make_query_create(priority="urgent"),
        )
        assert create_resp.status_code == 201
        query_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "open"

        # Step 2: Assign query
        assign_resp = await client.put(
            f"{API_PREFIX}/queries/{query_id}",
            json={"assigned_to": "Dr. Rachel Kim", "status": "assigned"},
        )
        assert assign_resp.status_code == 200
        assert assign_resp.json()["status"] == "assigned"

        # Step 3: Respond to query
        respond_resp = await client.post(
            f"{API_PREFIX}/queries/{query_id}/respond",
            json={"response_text": "Reviewed and confirmed.", "follow_up_required": False},
        )
        assert respond_resp.status_code == 200
        assert respond_resp.json()["status"] == "responded"


# =====================================================================
# QUERY RESOLUTION
# =====================================================================


class TestQueryResolution:
    """Test query resolution via the service."""

    def test_resolve_responded_query(self, svc: MedicalMonitorService):
        # MQ-003 has a response and is resolved already.
        # Use MQ-002 which is assigned - first respond, then resolve
        from app.schemas.medical_monitor import MedicalQueryResponse as MQR

        svc.respond_to_query("MQ-002", MQR(response_text="Eligible per protocol.", follow_up_required=False))
        result = svc.resolve_query("MQ-002")
        assert result is not None
        assert result.status == QueryStatus.RESOLVED
        assert result.resolution_date is not None

    def test_resolve_query_without_response_fails(self, svc: MedicalMonitorService):
        # MQ-005 is open with no response
        with pytest.raises(ValueError, match="no response provided"):
            svc.resolve_query("MQ-005")

    def test_resolve_nonexistent_query(self, svc: MedicalMonitorService):
        result = svc.resolve_query("MQ-NONEXISTENT")
        assert result is None


# =====================================================================
# PATIENT CASE REVIEW WORKFLOW
# =====================================================================


class TestCaseReviewWorkflow:
    """Test patient case review workflow."""

    @pytest.mark.anyio
    async def test_list_case_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"status": "pending"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_list_case_reviews_filter_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/case-reviews", params={"priority": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_case_reviews_sorted_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        data = resp.json()
        priority_order = {"critical": 0, "urgent": 1, "elevated": 2, "routine": 3}
        priorities = [priority_order.get(item["priority"], 4) for item in data["items"]]
        assert priorities == sorted(priorities)

    @pytest.mark.anyio
    async def test_create_case_review(self, client: AsyncClient):
        payload = _make_case_review_create()
        resp = await client.post(f"{API_PREFIX}/case-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-TEST-001"
        assert data["status"] == "pending"
        assert data["id"].startswith("CR-")

    @pytest.mark.anyio
    async def test_get_case_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_case_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_case_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/case-reviews/CR-003",
            json={"reviewer": "Dr. James Chen", "status": "in_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewer"] == "Dr. James Chen"
        assert data["status"] == "in_review"

    @pytest.mark.anyio
    async def test_update_case_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/case-reviews/CR-NONEXISTENT",
            json={"status": "in_review"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_case_review(self, client: AsyncClient):
        payload = {
            "clinical_summary": "32-year-old female, positive pregnancy test at Week 12 visit.",
            "findings": "Confirmed pregnancy. Last dose of IP 2 weeks prior.",
            "recommendations": "Discontinue IP. Follow pregnancy outcome per protocol.",
            "action_items": [
                "Report pregnancy to sponsor within 24 hours",
                "Initiate pregnancy follow-up form",
                "Monitor pregnancy outcome until resolution",
            ],
            "follow_up_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/case-reviews/CR-003/complete", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["review_date"] is not None
        assert data["clinical_summary"] is not None
        assert len(data["action_items"]) == 3

    @pytest.mark.anyio
    async def test_complete_already_completed_review_fails(self, client: AsyncClient):
        payload = {
            "clinical_summary": "Test",
            "findings": "Test",
            "recommendations": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/case-reviews/CR-001/complete", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_case_review_not_found(self, client: AsyncClient):
        payload = {
            "clinical_summary": "Test",
            "findings": "Test",
            "recommendations": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/case-reviews/CR-NONEXISTENT/complete", json=payload)
        assert resp.status_code == 404


# =====================================================================
# SAFETY TRENDS
# =====================================================================


class TestSafetyTrends:
    """Test safety trend analysis."""

    @pytest.mark.anyio
    async def test_list_all_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_trends_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-trends",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_trial_trends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-trends/{DUPIXENT_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_trend_direction_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-trends")
        data = resp.json()
        valid_directions = {"increasing", "stable", "decreasing"}
        for item in data["items"]:
            assert item["trend_direction"] in valid_directions

    def test_analyze_concerning_trends(self, svc: MedicalMonitorService):
        concerning = svc.analyze_trends(EYLEA_TRIAL)
        # Should include the hepatotoxicity trend (increasing + significant)
        assert len(concerning) > 0
        for t in concerning:
            assert (
                t.trend_direction == TrendDirection.INCREASING
                or t.statistical_significance
            )

    def test_analyze_trends_empty_trial(self, svc: MedicalMonitorService):
        concerning = svc.analyze_trends("NONEXISTENT-TRIAL")
        assert len(concerning) == 0


# =====================================================================
# MEDICAL MONITOR NOTES
# =====================================================================


class TestMedicalMonitorNotes:
    """Test medical monitor note operations."""

    @pytest.mark.anyio
    async def test_list_notes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_notes_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notes", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_notes_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notes", params={"category": "safety_review"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "safety_review"

    @pytest.mark.anyio
    async def test_create_note(self, client: AsyncClient):
        payload = _make_note_create()
        resp = await client.post(f"{API_PREFIX}/notes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test note"
        assert data["id"].startswith("MMN-")

    @pytest.mark.anyio
    async def test_create_note_with_references(self, client: AsyncClient):
        payload = _make_note_create(
            referenced_patients=["PAT-1001", "PAT-1002"],
            referenced_signals=["SIG-001"],
            visibility="sponsor",
        )
        resp = await client.post(f"{API_PREFIX}/notes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["referenced_patients"]) == 2
        assert data["referenced_signals"] == ["SIG-001"]
        assert data["visibility"] == "sponsor"


# =====================================================================
# METRICS
# =====================================================================


class TestMedicalMonitorMetrics:
    """Test medical monitor metrics aggregation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_signals"] >= 0
        assert data["pending_reviews"] >= 0
        assert data["overdue_queries"] >= 0
        assert data["avg_query_resolution_days"] >= 0
        assert data["assessments_due"] >= 0
        assert data["critical_cases"] >= 0
        assert data["active_trends"] >= 0

    def test_metrics_open_signals(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # SIG-001 (under_review), SIG-002 (confirmed), SIG-003 (escalated) are open
        # SIG-004 (refuted) is not open
        assert metrics.open_signals == 3

    def test_metrics_pending_reviews(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # CR-002 (in_review), CR-003 (pending), CR-004 (pending) are pending
        assert metrics.pending_reviews == 3

    def test_metrics_critical_cases(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # CR-002 is critical and in_review
        assert metrics.critical_cases >= 1

    def test_metrics_active_trends(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # TRD-001, TRD-002, TRD-003 are increasing
        assert metrics.active_trends == 3

    def test_metrics_avg_resolution_days(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # MQ-001 resolved in ~3 days, MQ-003 resolved in ~4 days
        assert metrics.avg_query_resolution_days > 0

    def test_metrics_assessments_due(self, svc: MedicalMonitorService):
        metrics = svc.get_metrics()
        # BRA-001 next_review_date is within 30 days, BRA-003 is within 30 days
        assert metrics.assessments_due >= 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_medical_monitor_service()
        svc2 = get_medical_monitor_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_medical_monitor_service()
        svc2 = reset_medical_monitor_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_monitor_service()
        # Create a signal then reset - should go back to 4
        from app.schemas.medical_monitor import SafetySignalCreate

        svc.create_signal(SafetySignalCreate(
            trial_id=EYLEA_TRIAL,
            signal_name="Extra signal",
            signal_type="Test",
            detected_date=datetime.now(timezone.utc),
            source="Test",
            description="Test",
            affected_patients_count=1,
            incidence_rate=1.0,
            expected_rate=0.5,
            risk_level=RiskLevel.LOW,
        ))
        assert len(svc.list_signals()) == 5
        svc2 = reset_medical_monitor_service()
        assert len(svc2.list_signals()) == 4


# =====================================================================
# ERROR CASES
# =====================================================================


class TestErrorCases:
    """Test error handling and edge cases."""

    @pytest.mark.anyio
    async def test_signal_404_detail_message(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals/NOPE")
        assert resp.status_code == 404
        body = resp.json()
        msg = body.get("detail") or body.get("message", "")
        assert "NOPE" in msg

    @pytest.mark.anyio
    async def test_assessment_404_detail_message(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/NOPE")
        assert resp.status_code == 404
        body = resp.json()
        msg = body.get("detail") or body.get("message", "")
        assert "NOPE" in msg

    @pytest.mark.anyio
    async def test_query_404_detail_message(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/NOPE")
        assert resp.status_code == 404
        body = resp.json()
        msg = body.get("detail") or body.get("message", "")
        assert "NOPE" in msg

    @pytest.mark.anyio
    async def test_case_review_404_detail_message(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews/NOPE")
        assert resp.status_code == 404
        body = resp.json()
        msg = body.get("detail") or body.get("message", "")
        assert "NOPE" in msg

    @pytest.mark.anyio
    async def test_create_signal_with_assigned_to(self, client: AsyncClient):
        payload = _make_signal_create(assigned_to="Dr. Test Monitor")
        resp = await client.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assigned_to"] == "Dr. Test Monitor"

    @pytest.mark.anyio
    async def test_create_query_with_patient_id(self, client: AsyncClient):
        payload = _make_query_create(patient_id="PAT-9999")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        assert resp.json()["patient_id"] == "PAT-9999"

    @pytest.mark.anyio
    async def test_create_case_review_with_reviewer(self, client: AsyncClient):
        payload = _make_case_review_create(
            reviewer="Dr. Rachel Kim",
            priority="critical",
        )
        resp = await client.post(f"{API_PREFIX}/case-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Dr. Rachel Kim"
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_signals_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_queries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_case_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_notes_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notes")
        assert resp.status_code == 200


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_assessment_outcomes_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefit-risk-assessments")
        data = resp.json()
        outcomes = {item["overall_outcome"] for item in data["items"]}
        assert "favorable" in outcomes
        assert "neutral" in outcomes

    @pytest.mark.anyio
    async def test_query_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "open" in statuses
        assert "assigned" in statuses
        assert "resolved" in statuses

    @pytest.mark.anyio
    async def test_case_review_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/case-reviews")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "pending" in statuses
        assert "completed" in statuses
        assert "in_review" in statuses

    @pytest.mark.anyio
    async def test_note_categories_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notes")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "safety_review" in categories
        assert "benefit_risk" in categories
        assert "medical_query" in categories

    @pytest.mark.anyio
    async def test_trend_directions_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-trends")
        data = resp.json()
        directions = {item["trend_direction"] for item in data["items"]}
        assert "increasing" in directions
        assert "stable" in directions
        assert "decreasing" in directions
