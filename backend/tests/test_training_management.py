"""Tests for Training & Competency Management (CLINICAL-13).

Covers:
- Seed data verification (courses, assignments, assessments, matrix)
- Course CRUD (create, read, update, delete, list, filter by type/role)
- Training assignment CRUD (create, read, update, delete, list, filter)
- Assignment completion with pass/fail scoring and certificate issuance
- Competency assessment CRUD and level tracking
- Training matrix (list, per-role lookup)
- Auto-assignment based on role/training matrix
- Certification expiry tracking and re-certification reminders
- Overdue assignment detection
- Compliance calculation by role and by site
- Competency gap analysis
- Training metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.training_management import (
    AutoAssignRequest,
    CompetencyAssessmentCreate,
    CompetencyLevel,
    CompletionStatus,
    TrainingAssignmentComplete,
    TrainingAssignmentCreate,
    TrainingCourseCreate,
    TrainingType,
)
from app.services.training_management_service import (
    TrainingManagementService,
    get_training_service,
    reset_training_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/training"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_training_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TrainingManagementService:
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


def _make_course_create(**overrides) -> dict:
    defaults = {
        "title": "Test Training Course",
        "training_type": "gcp_ich",
        "description": "A test training course for unit testing",
        "duration_hours": 2.0,
        "passing_score": 80.0,
        "version": "1.0",
        "expiry_months": 24,
        "required_for_roles": ["CRC"],
        "content_modules": ["Module 1", "Module 2"],
    }
    defaults.update(overrides)
    return defaults


def _make_assignment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "course_id": "TRN-001",
        "user_id": "USR-NEW",
        "user_name": "New User",
        "role": "CRC",
        "site_id": "SITE-101",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "user_id": "USR-001",
        "skill_area": "Test Skill Area",
        "current_level": "proficient",
        "assessor": "Test Assessor",
        "next_assessment_date": (now + timedelta(days=180)).isoformat(),
        "evidence": ["Evidence item 1", "Evidence item 2"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_courses_count(self, svc: TrainingManagementService):
        courses = svc.list_courses()
        assert len(courses) == 10

    def test_seed_courses_types(self, svc: TrainingManagementService):
        courses = svc.list_courses()
        types = {c.training_type for c in courses}
        assert TrainingType.GCP_ICH in types
        assert TrainingType.PROTOCOL_SPECIFIC in types
        assert TrainingType.SYSTEM in types
        assert TrainingType.SAFETY_REPORTING in types
        assert TrainingType.SOP in types
        assert TrainingType.REGULATORY in types
        assert TrainingType.DEVICE in types

    def test_seed_assignments_count(self, svc: TrainingManagementService):
        assignments = svc.list_assignments()
        assert len(assignments) == 40

    def test_seed_assignments_statuses(self, svc: TrainingManagementService):
        assignments = svc.list_assignments()
        statuses = {a.status for a in assignments}
        assert CompletionStatus.COMPLETED in statuses
        assert CompletionStatus.IN_PROGRESS in statuses
        assert CompletionStatus.NOT_STARTED in statuses

    def test_seed_assessments_count(self, svc: TrainingManagementService):
        assessments = svc.list_assessments()
        assert len(assessments) == 10

    def test_seed_assessments_levels(self, svc: TrainingManagementService):
        assessments = svc.list_assessments()
        levels = {a.current_level for a in assessments}
        assert CompetencyLevel.EXPERT in levels
        assert CompetencyLevel.PROFICIENT in levels
        assert CompetencyLevel.COMPETENT in levels
        assert CompetencyLevel.NOVICE in levels

    def test_seed_matrix_count(self, svc: TrainingManagementService):
        matrix = svc.list_training_matrix()
        assert len(matrix) == 5

    def test_seed_matrix_roles(self, svc: TrainingManagementService):
        matrix = svc.list_training_matrix()
        roles = {m.role for m in matrix}
        assert "PI" in roles
        assert "sub_investigator" in roles
        assert "CRC" in roles
        assert "study_nurse" in roles
        assert "pharmacist" in roles

    def test_seed_gcp_course_required_for_all_roles(self, svc: TrainingManagementService):
        course = svc.get_course("TRN-001")
        assert course is not None
        assert "PI" in course.required_for_roles
        assert "CRC" in course.required_for_roles
        assert "pharmacist" in course.required_for_roles

    def test_seed_course_has_modules(self, svc: TrainingManagementService):
        course = svc.get_course("TRN-001")
        assert course is not None
        assert len(course.content_modules) > 0


# =====================================================================
# COURSE CRUD
# =====================================================================


class TestCourseCrud:
    """Test training course create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_courses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_courses_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses", params={"training_type": "system"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["training_type"] == "system"

    @pytest.mark.anyio
    async def test_list_courses_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses", params={"role": "pharmacist"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "pharmacist" in item["required_for_roles"]

    @pytest.mark.anyio
    async def test_get_course(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses/TRN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TRN-001"
        assert "GCP" in data["title"]

    @pytest.mark.anyio
    async def test_get_course_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses/TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_course(self, client: AsyncClient):
        payload = _make_course_create()
        resp = await client.post(f"{API_PREFIX}/courses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Training Course"
        assert data["training_type"] == "gcp_ich"
        assert data["id"].startswith("TRN-")

    @pytest.mark.anyio
    async def test_create_course_with_all_fields(self, client: AsyncClient):
        payload = _make_course_create(
            title="Advanced Protocol Training",
            training_type="protocol_specific",
            description="Advanced protocol-specific training",
            duration_hours=6.0,
            passing_score=90.0,
            version="2.0",
            expiry_months=0,
            required_for_roles=["PI", "sub_investigator"],
            content_modules=["Module A", "Module B", "Module C"],
        )
        resp = await client.post(f"{API_PREFIX}/courses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["duration_hours"] == 6.0
        assert data["passing_score"] == 90.0
        assert len(data["content_modules"]) == 3

    @pytest.mark.anyio
    async def test_update_course(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/courses/TRN-001",
            json={"title": "Updated GCP Training", "version": "5.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated GCP Training"
        assert data["version"] == "5.0"

    @pytest.mark.anyio
    async def test_update_course_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/courses/TRN-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_course(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/courses/TRN-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/courses/TRN-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_course_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/courses/TRN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_courses_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses")
        assert resp.status_code == 200


# =====================================================================
# TRAINING ASSIGNMENT CRUD
# =====================================================================


class TestAssignmentCrud:
    """Test training assignment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_assignments_filter_user(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"user_id": "USR-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["user_id"] == "USR-001"

    @pytest.mark.anyio
    async def test_list_assignments_filter_course(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"course_id": "TRN-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["course_id"] == "TRN-001"

    @pytest.mark.anyio
    async def test_list_assignments_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_assignments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_assignments_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"role": "PI"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "PI"

    @pytest.mark.anyio
    async def test_get_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ASSIGN-0001"

    @pytest.mark.anyio
    async def test_get_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assignment(self, client: AsyncClient):
        payload = _make_assignment_create()
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "USR-NEW"
        assert data["course_id"] == "TRN-001"
        assert data["status"] == "not_started"
        assert data["id"].startswith("ASSIGN-")

    @pytest.mark.anyio
    async def test_create_assignment_invalid_course(self, client: AsyncClient):
        payload = _make_assignment_create(course_id="TRN-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_assignment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assignments/ASSIGN-0001",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assignments/ASSIGN-NONEXISTENT",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assignment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assignments/ASSIGN-0001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assignments/ASSIGN-0001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assignment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assignments/ASSIGN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ASSIGNMENT COMPLETION
# =====================================================================


class TestAssignmentCompletion:
    """Test completing training assignments with scoring."""

    @pytest.mark.anyio
    async def test_complete_assignment_pass(self, client: AsyncClient):
        # Find an in-progress assignment
        svc = get_training_service()
        in_progress = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.IN_PROGRESS
        ]
        assert len(in_progress) > 0
        assignment_id = in_progress[0].id

        payload = {"score": 95.0}
        resp = await client.post(f"{API_PREFIX}/assignments/{assignment_id}/complete", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["score"] == 95.0
        assert data["certificate_id"] is not None

    @pytest.mark.anyio
    async def test_complete_assignment_fail(self, client: AsyncClient):
        # Find an in-progress assignment
        svc = get_training_service()
        in_progress = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.IN_PROGRESS
        ]
        assert len(in_progress) > 0
        assignment_id = in_progress[0].id

        payload = {"score": 40.0}
        resp = await client.post(f"{API_PREFIX}/assignments/{assignment_id}/complete", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"  # Did not pass
        assert data["score"] == 40.0
        assert data["certificate_id"] is None

    @pytest.mark.anyio
    async def test_complete_assignment_already_completed(self, client: AsyncClient):
        # Find a completed assignment
        svc = get_training_service()
        completed = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.COMPLETED
        ]
        assert len(completed) > 0
        assignment_id = completed[0].id

        payload = {"score": 90.0}
        resp = await client.post(f"{API_PREFIX}/assignments/{assignment_id}/complete", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_complete_assignment_not_found(self, client: AsyncClient):
        payload = {"score": 85.0}
        resp = await client.post(
            f"{API_PREFIX}/assignments/ASSIGN-NONEXISTENT/complete", json=payload
        )
        assert resp.status_code == 404

    def test_complete_assignment_increments_attempts(self, svc: TrainingManagementService):
        in_progress = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.IN_PROGRESS
        ]
        assert len(in_progress) > 0
        assignment = in_progress[0]
        original_attempts = assignment.attempts

        result = svc.complete_assignment(
            assignment.id,
            TrainingAssignmentComplete(score=50.0),
        )
        assert result is not None
        assert result.attempts == original_attempts + 1

    def test_complete_assignment_sets_completion_date(self, svc: TrainingManagementService):
        in_progress = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.IN_PROGRESS
        ]
        assert len(in_progress) > 0
        assignment = in_progress[0]

        result = svc.complete_assignment(
            assignment.id,
            TrainingAssignmentComplete(score=95.0),
        )
        assert result is not None
        assert result.completion_date is not None


# =====================================================================
# COMPETENCY ASSESSMENTS
# =====================================================================


class TestCompetencyAssessments:
    """Test competency assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_assessments_filter_user(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"user_id": "USR-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["user_id"] == "USR-001"

    @pytest.mark.anyio
    async def test_list_assessments_filter_skill_area(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"skill_area": "injection"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "injection" in item["skill_area"].lower()

    @pytest.mark.anyio
    async def test_list_assessments_filter_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"level": "expert"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["current_level"] == "expert"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COMP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COMP-001"
        assert data["user_id"] == "USR-001"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COMP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "USR-001"
        assert data["skill_area"] == "Test Skill Area"
        assert data["current_level"] == "proficient"
        assert data["id"].startswith("COMP-")

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/COMP-007",
            json={"current_level": "competent", "assessor": "Dr. Updated Assessor"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_level"] == "competent"
        assert data["assessor"] == "Dr. Updated Assessor"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/COMP-NONEXISTENT",
            json={"current_level": "expert"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/COMP-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/COMP-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/COMP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRAINING MATRIX
# =====================================================================


class TestTrainingMatrix:
    """Test training matrix operations."""

    @pytest.mark.anyio
    async def test_get_full_matrix(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_get_role_matrix(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/matrix/PI")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "PI"
        assert len(data["required_courses"]) > 0

    @pytest.mark.anyio
    async def test_get_role_matrix_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/matrix/nonexistent_role")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_matrix_pharmacist_fewer_courses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/matrix/pharmacist")
        data = resp.json()
        assert len(data["required_courses"]) < 8  # Pharmacists need fewer courses

    @pytest.mark.anyio
    async def test_matrix_crc_has_edc_training(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/matrix/CRC")
        data = resp.json()
        assert "TRN-003" in data["required_courses"]  # EDC training

    def test_matrix_sorted_by_role(self, svc: TrainingManagementService):
        matrix = svc.list_training_matrix()
        roles = [m.role for m in matrix]
        assert roles == sorted(roles)

    def test_matrix_compliance_rates_valid(self, svc: TrainingManagementService):
        matrix = svc.list_training_matrix()
        for m in matrix:
            assert 0 <= m.compliance_rate <= 100


# =====================================================================
# AUTO-ASSIGNMENT
# =====================================================================


class TestAutoAssignment:
    """Test auto-assignment based on role/training matrix."""

    @pytest.mark.anyio
    async def test_auto_assign_new_user(self, client: AsyncClient):
        payload = {
            "user_id": "USR-NEW-001",
            "user_name": "New Staff Member",
            "role": "CRC",
            "site_id": "SITE-101",
        }
        resp = await client.post(f"{API_PREFIX}/auto-assign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignments_created"] > 0
        assert len(data["assignments"]) == data["assignments_created"]

    @pytest.mark.anyio
    async def test_auto_assign_invalid_role(self, client: AsyncClient):
        payload = {
            "user_id": "USR-NEW-002",
            "user_name": "Invalid Role User",
            "role": "nonexistent_role",
            "site_id": "SITE-101",
        }
        resp = await client.post(f"{API_PREFIX}/auto-assign", json=payload)
        assert resp.status_code == 400

    def test_auto_assign_skips_existing(self, svc: TrainingManagementService):
        """Auto-assign should not duplicate existing non-expired assignments."""
        # First auto-assign
        result1 = svc.auto_assign(AutoAssignRequest(
            user_id="USR-AUTO-TEST",
            user_name="Auto Test User",
            role="pharmacist",
            site_id="SITE-101",
        ))
        assert result1.assignments_created > 0

        # Second auto-assign should create 0 new
        result2 = svc.auto_assign(AutoAssignRequest(
            user_id="USR-AUTO-TEST",
            user_name="Auto Test User",
            role="pharmacist",
            site_id="SITE-101",
        ))
        assert result2.assignments_created == 0

    def test_auto_assign_creates_correct_courses(self, svc: TrainingManagementService):
        """Auto-assign should create assignments for all required courses."""
        matrix = svc.get_training_matrix("pharmacist")
        assert matrix is not None

        result = svc.auto_assign(AutoAssignRequest(
            user_id="USR-AUTO-PHARMA",
            user_name="New Pharmacist",
            role="pharmacist",
            site_id="SITE-102",
        ))
        assigned_courses = {a.course_id for a in result.assignments}
        for required_id in matrix.required_courses:
            assert required_id in assigned_courses


# =====================================================================
# CERTIFICATION EXPIRY
# =====================================================================


class TestCertificationExpiry:
    """Test certification expiry tracking."""

    @pytest.mark.anyio
    async def test_get_expiring_certifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications/expiring")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_get_expiring_certifications_custom_days(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications/expiring", params={"days": 90}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["days_until_expiry"] <= 90

    @pytest.mark.anyio
    async def test_get_recertification_reminders(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications/reminders")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_expiry_alerts_sorted_by_urgency(self, svc: TrainingManagementService):
        alerts = svc.get_expiring_certifications(days=365)
        if len(alerts) > 1:
            days = [a.days_until_expiry for a in alerts]
            assert days == sorted(days)

    def test_reminder_priorities(self, svc: TrainingManagementService):
        reminders = svc.get_recertification_reminders()
        valid_priorities = {"urgent", "warning", "info"}
        for r in reminders:
            assert r.priority in valid_priorities


# =====================================================================
# OVERDUE DETECTION
# =====================================================================


class TestOverdueDetection:
    """Test overdue assignment detection."""

    @pytest.mark.anyio
    async def test_get_overdue_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/overdue")
        assert resp.status_code == 200
        data = resp.json()
        now = datetime.now(timezone.utc)
        for item in data["items"]:
            due_date = datetime.fromisoformat(item["due_date"])
            assert due_date < now
            assert item["status"] in ("not_started", "in_progress")

    def test_overdue_sorted_by_due_date(self, svc: TrainingManagementService):
        overdue = svc.get_overdue_assignments()
        if len(overdue) > 1:
            dates = [a.due_date for a in overdue]
            assert dates == sorted(dates)

    def test_completed_not_in_overdue(self, svc: TrainingManagementService):
        overdue = svc.get_overdue_assignments()
        for a in overdue:
            assert a.status != CompletionStatus.COMPLETED

    def test_waived_not_in_overdue(self, svc: TrainingManagementService):
        overdue = svc.get_overdue_assignments()
        for a in overdue:
            assert a.status != CompletionStatus.WAIVED


# =====================================================================
# COMPLIANCE CALCULATION
# =====================================================================


class TestComplianceCalculation:
    """Test compliance rate calculations."""

    @pytest.mark.anyio
    async def test_compliance_by_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/by-role")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        for role, rate in data.items():
            assert 0 <= rate <= 100

    @pytest.mark.anyio
    async def test_compliance_by_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/by-site")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        for site, rate in data.items():
            assert 0 <= rate <= 100

    def test_compliance_by_role_includes_all_roles(self, svc: TrainingManagementService):
        compliance = svc.calculate_compliance_by_role()
        assignments = svc.list_assignments()
        roles_in_assignments = {a.role for a in assignments}
        for role in roles_in_assignments:
            assert role in compliance

    def test_compliance_by_site_includes_all_sites(self, svc: TrainingManagementService):
        compliance = svc.calculate_compliance_by_site()
        assignments = svc.list_assignments()
        sites_in_assignments = {a.site_id for a in assignments}
        for site in sites_in_assignments:
            assert site in compliance


# =====================================================================
# COMPETENCY GAP ANALYSIS
# =====================================================================


class TestCompetencyGapAnalysis:
    """Test competency gap analysis."""

    @pytest.mark.anyio
    async def test_get_competency_gap(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-gap/USR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "USR-001"
        assert "gaps" in data
        assert "recommendations" in data
        assert 0 <= data["overall_competency_score"] <= 100

    @pytest.mark.anyio
    async def test_get_competency_gap_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-gap/USR-NONEXISTENT")
        assert resp.status_code == 404

    def test_gap_analysis_identifies_incomplete_training(self, svc: TrainingManagementService):
        # USR-006 is a novice in safety reporting
        analysis = svc.get_competency_gap_analysis("USR-006")
        assert analysis is not None
        # Should have some gaps or recommendations
        assert len(analysis.gaps) > 0 or len(analysis.recommendations) > 0

    def test_gap_analysis_novice_has_lower_score(self, svc: TrainingManagementService):
        # USR-006 has novice-level assessment
        analysis_novice = svc.get_competency_gap_analysis("USR-006")
        # USR-001 has expert-level assessment
        analysis_expert = svc.get_competency_gap_analysis("USR-001")
        assert analysis_novice is not None
        assert analysis_expert is not None
        assert analysis_novice.overall_competency_score <= analysis_expert.overall_competency_score

    def test_gap_analysis_includes_role(self, svc: TrainingManagementService):
        analysis = svc.get_competency_gap_analysis("USR-001")
        assert analysis is not None
        assert analysis.role == "PI"


# =====================================================================
# TRAINING METRICS
# =====================================================================


class TestTrainingMetrics:
    """Test training metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 10
        assert data["total_assignments"] == 40
        assert 0 <= data["completion_rate"] <= 100
        assert data["overdue_count"] >= 0
        assert 0 <= data["avg_score"] <= 100
        assert data["certifications_expiring_30d"] >= 0
        assert isinstance(data["compliance_by_role"], dict)
        assert isinstance(data["compliance_by_site"], dict)

    def test_metrics_completion_rate_matches_assignments(self, svc: TrainingManagementService):
        metrics = svc.get_metrics()
        assignments = svc.list_assignments()
        completed = sum(
            1 for a in assignments
            if a.status in (CompletionStatus.COMPLETED, CompletionStatus.WAIVED)
        )
        expected_rate = round(completed / max(1, len(assignments)) * 100, 1)
        assert metrics.completion_rate == expected_rate

    def test_metrics_overdue_count_matches(self, svc: TrainingManagementService):
        metrics = svc.get_metrics()
        overdue = svc.get_overdue_assignments()
        assert metrics.overdue_count == len(overdue)

    def test_metrics_avg_score_reasonable(self, svc: TrainingManagementService):
        metrics = svc.get_metrics()
        # Average score should be reasonable for our seed data
        assert metrics.avg_score > 0

    def test_metrics_compliance_by_role_non_empty(self, svc: TrainingManagementService):
        metrics = svc.get_metrics()
        assert len(metrics.compliance_by_role) > 0

    def test_metrics_compliance_by_site_non_empty(self, svc: TrainingManagementService):
        metrics = svc.get_metrics()
        assert len(metrics.compliance_by_site) > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_training_service()
        svc2 = get_training_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_training_service()
        svc2 = reset_training_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_training_service()
        svc.delete_course("TRN-001")
        assert svc.get_course("TRN-001") is None
        svc2 = reset_training_service()
        assert svc2.get_course("TRN-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_assignments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_course_minimum_fields(self, client: AsyncClient):
        payload = {
            "title": "Minimal Course",
            "training_type": "sop",
            "description": "A minimal course",
            "duration_hours": 1.0,
        }
        resp = await client.post(f"{API_PREFIX}/courses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["passing_score"] == 80.0  # default
        assert data["version"] == "1.0"  # default
        assert data["expiry_months"] == 24  # default

    @pytest.mark.anyio
    async def test_create_course_device_type(self, client: AsyncClient):
        payload = _make_course_create(
            title="Device Training",
            training_type="device",
            description="Medical device training",
        )
        resp = await client.post(f"{API_PREFIX}/courses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["training_type"] == "device"

    @pytest.mark.anyio
    async def test_create_course_data_entry_type(self, client: AsyncClient):
        payload = _make_course_create(
            title="Data Entry Training",
            training_type="data_entry",
            description="Data entry best practices",
        )
        resp = await client.post(f"{API_PREFIX}/courses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["training_type"] == "data_entry"

    @pytest.mark.anyio
    async def test_update_course_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/courses/TRN-001",
            json={"passing_score": 85.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passing_score"] == 85.0
        assert data["title"] is not None  # Other fields preserved

    @pytest.mark.anyio
    async def test_update_assignment_score(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assignments/ASSIGN-0001",
            json={"score": 92.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 92.0

    @pytest.mark.anyio
    async def test_list_courses_filter_safety_reporting(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses", params={"training_type": "safety_reporting"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_courses_filter_regulatory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses", params={"training_type": "regulatory"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2  # Informed consent + GDPR

    @pytest.mark.anyio
    async def test_assessment_evidence_is_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/COMP-001")
        data = resp.json()
        assert isinstance(data["evidence"], list)
        assert len(data["evidence"]) > 0

    @pytest.mark.anyio
    async def test_course_content_modules_is_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses/TRN-001")
        data = resp.json()
        assert isinstance(data["content_modules"], list)
        assert len(data["content_modules"]) > 0


# =====================================================================
# TRAINING TYPE ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_training_types_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses")
        data = resp.json()
        types = {item["training_type"] for item in data["items"]}
        assert "gcp_ich" in types
        assert "protocol_specific" in types
        assert "system" in types
        assert "safety_reporting" in types
        assert "sop" in types
        assert "regulatory" in types
        assert "device" in types

    @pytest.mark.anyio
    async def test_completion_statuses_in_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "in_progress" in statuses
        assert "not_started" in statuses

    @pytest.mark.anyio
    async def test_competency_levels_in_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        levels = {item["current_level"] for item in data["items"]}
        assert "expert" in levels
        assert "proficient" in levels
        assert "competent" in levels
        assert "novice" in levels


# =====================================================================
# COURSE DETAILS
# =====================================================================


class TestCourseDetails:
    """Test detailed course information."""

    @pytest.mark.anyio
    async def test_course_has_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses/TRN-001")
        data = resp.json()
        assert "id" in data
        assert "title" in data
        assert "training_type" in data
        assert "description" in data
        assert "duration_hours" in data
        assert "passing_score" in data
        assert "version" in data
        assert "effective_date" in data
        assert "expiry_months" in data
        assert "required_for_roles" in data
        assert "content_modules" in data

    @pytest.mark.anyio
    async def test_course_duration_positive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses")
        data = resp.json()
        for item in data["items"]:
            assert item["duration_hours"] > 0

    @pytest.mark.anyio
    async def test_course_passing_score_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses")
        data = resp.json()
        for item in data["items"]:
            assert 0 <= item["passing_score"] <= 100

    @pytest.mark.anyio
    async def test_protocol_specific_no_expiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/courses/TRN-002")
        data = resp.json()
        assert data["training_type"] == "protocol_specific"
        assert data["expiry_months"] == 0


# =====================================================================
# ASSIGNMENT DETAILS
# =====================================================================


class TestAssignmentDetails:
    """Test detailed assignment information."""

    @pytest.mark.anyio
    async def test_assignment_has_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-0001")
        data = resp.json()
        assert "id" in data
        assert "course_id" in data
        assert "user_id" in data
        assert "user_name" in data
        assert "role" in data
        assert "site_id" in data
        assert "assigned_date" in data
        assert "due_date" in data
        assert "status" in data
        assert "attempts" in data

    @pytest.mark.anyio
    async def test_completed_assignment_has_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"status": "completed"})
        data = resp.json()
        for item in data["items"]:
            if item["status"] == "completed":
                assert item["score"] is not None
                assert item["score"] > 0

    @pytest.mark.anyio
    async def test_completed_assignment_has_certificate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assignments", params={"status": "completed"})
        data = resp.json()
        for item in data["items"]:
            if item["status"] == "completed":
                assert item["certificate_id"] is not None


# =====================================================================
# MULTIPLE OPERATIONS
# =====================================================================


class TestMultipleOperations:
    """Test sequences of operations."""

    @pytest.mark.anyio
    async def test_create_and_complete_assignment(self, client: AsyncClient):
        """Create a new assignment and complete it."""
        # Create
        payload = _make_assignment_create()
        resp = await client.post(f"{API_PREFIX}/assignments", json=payload)
        assert resp.status_code == 201
        assignment_id = resp.json()["id"]

        # Complete with passing score
        resp2 = await client.post(
            f"{API_PREFIX}/assignments/{assignment_id}/complete",
            json={"score": 95.0},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "completed"
        assert data["certificate_id"] is not None

    @pytest.mark.anyio
    async def test_create_course_and_assign(self, client: AsyncClient):
        """Create a new course and then assign it."""
        # Create course
        course_payload = _make_course_create(title="New Custom Course")
        resp = await client.post(f"{API_PREFIX}/courses", json=course_payload)
        assert resp.status_code == 201
        course_id = resp.json()["id"]

        # Assign
        now = datetime.now(timezone.utc)
        assign_payload = _make_assignment_create(
            course_id=course_id,
            due_date=(now + timedelta(days=60)).isoformat(),
        )
        resp2 = await client.post(f"{API_PREFIX}/assignments", json=assign_payload)
        assert resp2.status_code == 201
        assert resp2.json()["course_id"] == course_id

    @pytest.mark.anyio
    async def test_auto_assign_and_verify_assignments(self, client: AsyncClient):
        """Auto-assign and verify assignments are created."""
        payload = {
            "user_id": "USR-VERIFY-001",
            "user_name": "Verification User",
            "role": "pharmacist",
            "site_id": "SITE-101",
        }
        resp = await client.post(f"{API_PREFIX}/auto-assign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        created_count = data["assignments_created"]

        # Verify assignments exist
        resp2 = await client.get(
            f"{API_PREFIX}/assignments", params={"user_id": "USR-VERIFY-001"}
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total"] == created_count

    @pytest.mark.anyio
    async def test_update_assessment_level_progression(self, client: AsyncClient):
        """Verify competency level progression."""
        # Start at novice
        resp = await client.get(f"{API_PREFIX}/assessments/COMP-007")
        assert resp.json()["current_level"] == "novice"

        # Progress to competent
        resp2 = await client.put(
            f"{API_PREFIX}/assessments/COMP-007",
            json={"current_level": "competent"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["current_level"] == "competent"

        # Progress to proficient
        resp3 = await client.put(
            f"{API_PREFIX}/assessments/COMP-007",
            json={"current_level": "proficient"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["current_level"] == "proficient"

    @pytest.mark.anyio
    async def test_metrics_after_completing_assignment(self, client: AsyncClient):
        """Metrics should update after completing an assignment."""
        # Get initial metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial_rate = resp1.json()["completion_rate"]

        # Complete an in-progress assignment
        svc = get_training_service()
        in_progress = [
            a for a in svc.list_assignments()
            if a.status == CompletionStatus.IN_PROGRESS
        ]
        if in_progress:
            resp2 = await client.post(
                f"{API_PREFIX}/assignments/{in_progress[0].id}/complete",
                json={"score": 95.0},
            )
            assert resp2.status_code == 200

            # Check metrics updated
            resp3 = await client.get(f"{API_PREFIX}/metrics")
            new_rate = resp3.json()["completion_rate"]
            assert new_rate >= initial_rate
