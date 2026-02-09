"""Training & Competency Management Service (CLINICAL-13).

Manages training operations including course definitions, training assignments with
completion tracking, competency assessments, training matrix by role, certification
management with expiry tracking, auto-assignment, and compliance reporting.

Usage:
    from app.services.training_management_service import (
        get_training_service,
    )

    svc = get_training_service()
    courses = svc.list_courses()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.training_management import (
    AutoAssignRequest,
    AutoAssignResponse,
    CertificationExpiryAlert,
    CompetencyAssessment,
    CompetencyAssessmentCreate,
    CompetencyAssessmentUpdate,
    CompetencyGapAnalysis,
    CompetencyLevel,
    CompletionStatus,
    RecertificationReminder,
    TrainingAssignment,
    TrainingAssignmentComplete,
    TrainingAssignmentCreate,
    TrainingAssignmentUpdate,
    TrainingCourse,
    TrainingCourseCreate,
    TrainingCourseUpdate,
    TrainingMatrix,
    TrainingMetrics,
    TrainingType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Certification expiry warning threshold
EXPIRY_WARNING_DAYS = 30

# Competency level numeric mapping
COMPETENCY_SCORES = {
    CompetencyLevel.NOVICE: 25.0,
    CompetencyLevel.COMPETENT: 50.0,
    CompetencyLevel.PROFICIENT: 75.0,
    CompetencyLevel.EXPERT: 100.0,
}


class TrainingManagementService:
    """In-memory Training & Competency Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._courses: dict[str, TrainingCourse] = {}
        self._assignments: dict[str, TrainingAssignment] = {}
        self._assessments: dict[str, CompetencyAssessment] = {}
        self._matrix: dict[str, TrainingMatrix] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic training & competency data."""
        now = datetime.now(timezone.utc)

        # --- 10 Training Courses ---
        courses_data = [
            {
                "id": "TRN-001",
                "title": "GCP/ICH E6(R2) Good Clinical Practice",
                "training_type": TrainingType.GCP_ICH,
                "description": "Comprehensive GCP training covering ICH E6(R2) guidelines, "
                "investigator responsibilities, and ethical conduct of clinical trials",
                "duration_hours": 8.0,
                "passing_score": 80.0,
                "version": "4.0",
                "effective_date": now - timedelta(days=365),
                "expiry_months": 36,
                "required_for_roles": ["PI", "sub_investigator", "CRC", "study_nurse", "pharmacist"],
                "content_modules": [
                    "History and Development of GCP",
                    "Principles of ICH E6(R2)",
                    "IRB/IEC Responsibilities",
                    "Investigator Responsibilities",
                    "Sponsor Responsibilities",
                    "Essential Documents",
                ],
            },
            {
                "id": "TRN-002",
                "title": "Protocol-Specific Training: EYLEA Retinal Study",
                "training_type": TrainingType.PROTOCOL_SPECIFIC,
                "description": "Protocol-specific training for the EYLEA retinal study including "
                "inclusion/exclusion criteria, study procedures, and endpoint assessments",
                "duration_hours": 4.0,
                "passing_score": 85.0,
                "version": "2.1",
                "effective_date": now - timedelta(days=180),
                "expiry_months": 0,
                "required_for_roles": ["PI", "sub_investigator", "CRC", "study_nurse"],
                "content_modules": [
                    "Protocol Overview",
                    "Inclusion/Exclusion Criteria",
                    "Study Procedures",
                    "Ocular Assessments",
                    "Safety Reporting Requirements",
                ],
            },
            {
                "id": "TRN-003",
                "title": "EDC System Training (Medidata Rave)",
                "training_type": TrainingType.SYSTEM,
                "description": "Electronic Data Capture system training covering data entry, "
                "query resolution, e-signature, and audit trail requirements",
                "duration_hours": 3.0,
                "passing_score": 90.0,
                "version": "5.0",
                "effective_date": now - timedelta(days=120),
                "expiry_months": 24,
                "required_for_roles": ["CRC", "study_nurse", "sub_investigator"],
                "content_modules": [
                    "EDC System Overview",
                    "Data Entry Best Practices",
                    "Query Management",
                    "Electronic Signatures (21 CFR Part 11)",
                    "Audit Trail and Data Integrity",
                ],
            },
            {
                "id": "TRN-004",
                "title": "SAE Reporting Procedures",
                "training_type": TrainingType.SAFETY_REPORTING,
                "description": "Serious Adverse Event reporting including timelines, causality "
                "assessment, narrative writing, and regulatory reporting requirements",
                "duration_hours": 2.5,
                "passing_score": 85.0,
                "version": "3.0",
                "effective_date": now - timedelta(days=200),
                "expiry_months": 24,
                "required_for_roles": ["PI", "sub_investigator", "CRC", "study_nurse"],
                "content_modules": [
                    "SAE Definitions and Classification",
                    "Reporting Timelines",
                    "Causality Assessment",
                    "SAE Narrative Writing",
                    "Regulatory Reporting (FDA, EMA)",
                ],
            },
            {
                "id": "TRN-005",
                "title": "Interactive Response Technology (IRT) Randomization System",
                "training_type": TrainingType.SYSTEM,
                "description": "IRT/IWRS training for randomization, drug dispensing, "
                "and supply management procedures",
                "duration_hours": 2.0,
                "passing_score": 80.0,
                "version": "2.0",
                "effective_date": now - timedelta(days=150),
                "expiry_months": 24,
                "required_for_roles": ["CRC", "pharmacist"],
                "content_modules": [
                    "IRT System Overview",
                    "Randomization Procedures",
                    "Drug Dispensing Workflow",
                    "Emergency Unblinding",
                ],
            },
            {
                "id": "TRN-006",
                "title": "Investigational Medicinal Product (IMP) Handling",
                "training_type": TrainingType.SOP,
                "description": "Standard operating procedures for IMP receipt, storage, "
                "dispensing, accountability, and destruction",
                "duration_hours": 3.0,
                "passing_score": 85.0,
                "version": "2.5",
                "effective_date": now - timedelta(days=250),
                "expiry_months": 24,
                "required_for_roles": ["pharmacist", "study_nurse"],
                "content_modules": [
                    "IMP Receipt and Verification",
                    "Storage Requirements",
                    "Dispensing Procedures",
                    "Accountability Logs",
                    "Returns and Destruction",
                ],
            },
            {
                "id": "TRN-007",
                "title": "Informed Consent Process Training",
                "training_type": TrainingType.REGULATORY,
                "description": "Regulatory requirements for the informed consent process "
                "including capacity assessment, re-consent, and vulnerable populations",
                "duration_hours": 2.0,
                "passing_score": 85.0,
                "version": "3.0",
                "effective_date": now - timedelta(days=300),
                "expiry_months": 36,
                "required_for_roles": ["PI", "sub_investigator", "CRC"],
                "content_modules": [
                    "Regulatory Framework (45 CFR 46, ICH E6)",
                    "Elements of Informed Consent",
                    "Capacity Assessment",
                    "Re-consent Procedures",
                    "Vulnerable Populations",
                ],
            },
            {
                "id": "TRN-008",
                "title": "Medical Device Training: Injection Pen Administration",
                "training_type": TrainingType.DEVICE,
                "description": "Training on the use of pre-filled injection pens for "
                "subcutaneous administration of study drug",
                "duration_hours": 1.5,
                "passing_score": 90.0,
                "version": "1.0",
                "effective_date": now - timedelta(days=90),
                "expiry_months": 12,
                "required_for_roles": ["study_nurse", "sub_investigator"],
                "content_modules": [
                    "Device Overview and Components",
                    "Injection Technique",
                    "Patient Training Procedures",
                    "Device Complaints and Malfunctions",
                ],
            },
            {
                "id": "TRN-009",
                "title": "GDPR and Data Privacy in Clinical Trials",
                "training_type": TrainingType.REGULATORY,
                "description": "General Data Protection Regulation compliance training "
                "covering data subject rights, consent, data transfers, and breach reporting",
                "duration_hours": 2.0,
                "passing_score": 80.0,
                "version": "2.0",
                "effective_date": now - timedelta(days=180),
                "expiry_months": 24,
                "required_for_roles": ["PI", "sub_investigator", "CRC", "study_nurse", "pharmacist"],
                "content_modules": [
                    "GDPR Principles and Scope",
                    "Data Subject Rights",
                    "Lawful Basis for Processing",
                    "International Data Transfers",
                    "Breach Notification",
                ],
            },
            {
                "id": "TRN-010",
                "title": "Protocol-Specific Training: DUPIXENT Dermatology Study",
                "training_type": TrainingType.PROTOCOL_SPECIFIC,
                "description": "Protocol-specific training for the DUPIXENT dermatology study "
                "including EASI scoring, photography standards, and ePRO completion",
                "duration_hours": 3.5,
                "passing_score": 85.0,
                "version": "1.2",
                "effective_date": now - timedelta(days=120),
                "expiry_months": 0,
                "required_for_roles": ["PI", "sub_investigator", "CRC", "study_nurse"],
                "content_modules": [
                    "Protocol Overview and Endpoints",
                    "EASI Scoring Methodology",
                    "Photography Standards",
                    "ePRO Device Training",
                    "Biomarker Sample Collection",
                ],
            },
        ]

        for c in courses_data:
            self._courses[c["id"]] = TrainingCourse(**c)

        # --- Training Matrix for 5 Roles ---
        matrix_data = [
            {
                "role": "PI",
                "required_courses": ["TRN-001", "TRN-002", "TRN-004", "TRN-007", "TRN-009", "TRN-010"],
                "optional_courses": ["TRN-003", "TRN-008"],
                "compliance_rate": 92.0,
            },
            {
                "role": "sub_investigator",
                "required_courses": ["TRN-001", "TRN-002", "TRN-003", "TRN-004", "TRN-007", "TRN-008", "TRN-009", "TRN-010"],
                "optional_courses": ["TRN-005"],
                "compliance_rate": 85.0,
            },
            {
                "role": "CRC",
                "required_courses": ["TRN-001", "TRN-002", "TRN-003", "TRN-004", "TRN-005", "TRN-007", "TRN-009", "TRN-010"],
                "optional_courses": ["TRN-006"],
                "compliance_rate": 88.0,
            },
            {
                "role": "study_nurse",
                "required_courses": ["TRN-001", "TRN-002", "TRN-003", "TRN-004", "TRN-006", "TRN-008", "TRN-009", "TRN-010"],
                "optional_courses": ["TRN-007"],
                "compliance_rate": 90.0,
            },
            {
                "role": "pharmacist",
                "required_courses": ["TRN-001", "TRN-005", "TRN-006", "TRN-009"],
                "optional_courses": ["TRN-004"],
                "compliance_rate": 95.0,
            },
        ]

        for m in matrix_data:
            self._matrix[m["role"]] = TrainingMatrix(**m)

        # --- 40 Training Assignments across 15 users ---
        users = [
            ("USR-001", "Dr. Sarah Chen", "PI", "SITE-101"),
            ("USR-002", "Dr. James Wilson", "PI", "SITE-102"),
            ("USR-003", "Dr. Maria Garcia", "PI", "SITE-103"),
            ("USR-004", "Dr. Robert Kim", "sub_investigator", "SITE-101"),
            ("USR-005", "Dr. Lisa Patel", "sub_investigator", "SITE-102"),
            ("USR-006", "Dr. Michael Torres", "sub_investigator", "SITE-103"),
            ("USR-007", "Emily Davis", "CRC", "SITE-101"),
            ("USR-008", "Jennifer Martinez", "CRC", "SITE-102"),
            ("USR-009", "David Lee", "CRC", "SITE-103"),
            ("USR-010", "Amanda Thompson", "study_nurse", "SITE-101"),
            ("USR-011", "Rachel Brown", "study_nurse", "SITE-102"),
            ("USR-012", "Jessica White", "study_nurse", "SITE-103"),
            ("USR-013", "Mark Johnson", "pharmacist", "SITE-101"),
            ("USR-014", "Laura Anderson", "pharmacist", "SITE-102"),
            ("USR-015", "Kevin Wright", "pharmacist", "SITE-103"),
        ]

        assignment_counter = 0
        assignments_data = []

        # Generate assignments based on training matrix
        for user_id, user_name, role, site_id in users:
            matrix_entry = self._matrix.get(role)
            if matrix_entry is None:
                continue

            for course_id in matrix_entry.required_courses:
                assignment_counter += 1
                course = self._courses.get(course_id)
                if course is None:
                    continue

                # Vary the status based on assignment number for realistic spread
                idx = assignment_counter % 10
                if idx < 5:
                    # Completed assignments
                    comp_date = now - timedelta(days=30 + idx * 20)
                    status = CompletionStatus.COMPLETED
                    score = 82.0 + idx * 3.0
                    attempts = 1
                    cert_id = f"CERT-{assignment_counter:04d}"
                elif idx < 7:
                    # In progress
                    comp_date = None
                    status = CompletionStatus.IN_PROGRESS
                    score = None
                    attempts = 0
                    cert_id = None
                elif idx < 8:
                    # Not started
                    comp_date = None
                    status = CompletionStatus.NOT_STARTED
                    score = None
                    attempts = 0
                    cert_id = None
                elif idx < 9:
                    # Expired - completed long ago
                    comp_date = now - timedelta(days=800)
                    status = CompletionStatus.EXPIRED
                    score = 85.0
                    attempts = 1
                    cert_id = f"CERT-{assignment_counter:04d}"
                else:
                    # Waived
                    comp_date = None
                    status = CompletionStatus.WAIVED
                    score = None
                    attempts = 0
                    cert_id = None

                assignments_data.append({
                    "id": f"ASSIGN-{assignment_counter:04d}",
                    "course_id": course_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "role": role,
                    "site_id": site_id,
                    "assigned_date": now - timedelta(days=60 + idx * 5),
                    "due_date": now - timedelta(days=10) if idx >= 7 else now + timedelta(days=30),
                    "completion_date": comp_date,
                    "status": status,
                    "score": score,
                    "attempts": attempts,
                    "certificate_id": cert_id,
                })

                # Stop at 40 assignments
                if assignment_counter >= 40:
                    break
            if assignment_counter >= 40:
                break

        for a in assignments_data:
            self._assignments[a["id"]] = TrainingAssignment(**a)

        # --- 10 Competency Assessments ---
        assessments_data = [
            {
                "id": "COMP-001",
                "user_id": "USR-001",
                "skill_area": "Clinical Trial Management",
                "current_level": CompetencyLevel.EXPERT,
                "assessed_date": now - timedelta(days=60),
                "assessor": "Dr. Thomas Reed (Medical Director)",
                "next_assessment_date": now + timedelta(days=305),
                "evidence": [
                    "15 years PI experience",
                    "50+ trials completed",
                    "GCP certification current",
                ],
            },
            {
                "id": "COMP-002",
                "user_id": "USR-004",
                "skill_area": "Patient Assessment",
                "current_level": CompetencyLevel.PROFICIENT,
                "assessed_date": now - timedelta(days=45),
                "assessor": "Dr. Sarah Chen (PI)",
                "next_assessment_date": now + timedelta(days=320),
                "evidence": [
                    "5 years sub-investigator experience",
                    "Board certified ophthalmology",
                    "Protocol training completed",
                ],
            },
            {
                "id": "COMP-003",
                "user_id": "USR-007",
                "skill_area": "Data Collection and Entry",
                "current_level": CompetencyLevel.PROFICIENT,
                "assessed_date": now - timedelta(days=30),
                "assessor": "Jennifer Lee (Clinical Ops Manager)",
                "next_assessment_date": now + timedelta(days=335),
                "evidence": [
                    "3 years CRC experience",
                    "EDC certification current",
                    "Zero data entry errors last quarter",
                ],
            },
            {
                "id": "COMP-004",
                "user_id": "USR-010",
                "skill_area": "Injection Technique",
                "current_level": CompetencyLevel.EXPERT,
                "assessed_date": now - timedelta(days=20),
                "assessor": "Dr. Sarah Chen (PI)",
                "next_assessment_date": now + timedelta(days=345),
                "evidence": [
                    "10 years nursing experience",
                    "Device training completed",
                    "Observed competency check passed",
                ],
            },
            {
                "id": "COMP-005",
                "user_id": "USR-013",
                "skill_area": "IMP Management",
                "current_level": CompetencyLevel.EXPERT,
                "assessed_date": now - timedelta(days=15),
                "assessor": "Laura Anderson (Pharmacy Director)",
                "next_assessment_date": now + timedelta(days=350),
                "evidence": [
                    "8 years clinical pharmacy experience",
                    "IMP handling certification",
                    "Perfect accountability audit record",
                ],
            },
            {
                "id": "COMP-006",
                "user_id": "USR-009",
                "skill_area": "Informed Consent Process",
                "current_level": CompetencyLevel.COMPETENT,
                "assessed_date": now - timedelta(days=40),
                "assessor": "Dr. Maria Garcia (PI)",
                "next_assessment_date": now + timedelta(days=145),
                "evidence": [
                    "1 year CRC experience",
                    "Consent training completed",
                    "Observed 10 consent encounters",
                ],
            },
            {
                "id": "COMP-007",
                "user_id": "USR-006",
                "skill_area": "Safety Reporting",
                "current_level": CompetencyLevel.NOVICE,
                "assessed_date": now - timedelta(days=10),
                "assessor": "Dr. Maria Garcia (PI)",
                "next_assessment_date": now + timedelta(days=80),
                "evidence": [
                    "New sub-investigator (6 months)",
                    "SAE training in progress",
                ],
            },
            {
                "id": "COMP-008",
                "user_id": "USR-011",
                "skill_area": "Phlebotomy and Sample Processing",
                "current_level": CompetencyLevel.PROFICIENT,
                "assessed_date": now - timedelta(days=25),
                "assessor": "Amanda Thompson (Lead Nurse)",
                "next_assessment_date": now + timedelta(days=340),
                "evidence": [
                    "5 years nursing experience",
                    "Phlebotomy certification current",
                    "Lab kit processing training completed",
                ],
            },
            {
                "id": "COMP-009",
                "user_id": "USR-008",
                "skill_area": "Regulatory Document Management",
                "current_level": CompetencyLevel.COMPETENT,
                "assessed_date": now - timedelta(days=50),
                "assessor": "Jennifer Lee (Clinical Ops Manager)",
                "next_assessment_date": now + timedelta(days=130),
                "evidence": [
                    "2 years CRC experience",
                    "eTMF training completed",
                    "Satisfactory audit findings",
                ],
            },
            {
                "id": "COMP-010",
                "user_id": "USR-015",
                "skill_area": "Drug Accountability",
                "current_level": CompetencyLevel.COMPETENT,
                "assessed_date": now - timedelta(days=35),
                "assessor": "Mark Johnson (Lead Pharmacist)",
                "next_assessment_date": now + timedelta(days=330),
                "evidence": [
                    "1 year clinical pharmacy experience",
                    "IMP handling training completed",
                    "Supervised dispensing period complete",
                ],
            },
        ]

        for a in assessments_data:
            self._assessments[a["id"]] = CompetencyAssessment(**a)

    # ------------------------------------------------------------------
    # Course Management
    # ------------------------------------------------------------------

    def list_courses(
        self,
        *,
        training_type: TrainingType | None = None,
        role: str | None = None,
    ) -> list[TrainingCourse]:
        """List training courses with optional filters."""
        with self._lock:
            result = list(self._courses.values())

        if training_type is not None:
            result = [c for c in result if c.training_type == training_type]
        if role is not None:
            result = [c for c in result if role in c.required_for_roles]

        return sorted(result, key=lambda c: c.id)

    def get_course(self, course_id: str) -> TrainingCourse | None:
        """Get a single course by ID."""
        with self._lock:
            return self._courses.get(course_id)

    def create_course(self, payload: TrainingCourseCreate) -> TrainingCourse:
        """Create a new training course."""
        now = datetime.now(timezone.utc)
        course_id = f"TRN-{uuid4().hex[:8].upper()}"
        course = TrainingCourse(
            id=course_id,
            title=payload.title,
            training_type=payload.training_type,
            description=payload.description,
            duration_hours=payload.duration_hours,
            passing_score=payload.passing_score,
            version=payload.version,
            effective_date=now,
            expiry_months=payload.expiry_months,
            required_for_roles=payload.required_for_roles,
            content_modules=payload.content_modules,
        )
        with self._lock:
            self._courses[course_id] = course
        logger.info("Created training course %s: %s", course_id, payload.title)
        return course

    def update_course(self, course_id: str, payload: TrainingCourseUpdate) -> TrainingCourse | None:
        """Update an existing training course."""
        with self._lock:
            existing = self._courses.get(course_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TrainingCourse(**data)
            self._courses[course_id] = updated
        return updated

    def delete_course(self, course_id: str) -> bool:
        """Delete a course. Returns True if deleted, False if not found."""
        with self._lock:
            if course_id in self._courses:
                del self._courses[course_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Training Assignments
    # ------------------------------------------------------------------

    def list_assignments(
        self,
        *,
        user_id: str | None = None,
        course_id: str | None = None,
        site_id: str | None = None,
        status: CompletionStatus | None = None,
        role: str | None = None,
    ) -> list[TrainingAssignment]:
        """List training assignments with optional filters."""
        with self._lock:
            result = list(self._assignments.values())

        if user_id is not None:
            result = [a for a in result if a.user_id == user_id]
        if course_id is not None:
            result = [a for a in result if a.course_id == course_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if status is not None:
            result = [a for a in result if a.status == status]
        if role is not None:
            result = [a for a in result if a.role == role]

        return sorted(result, key=lambda a: a.assigned_date, reverse=True)

    def get_assignment(self, assignment_id: str) -> TrainingAssignment | None:
        """Get a single assignment by ID."""
        with self._lock:
            return self._assignments.get(assignment_id)

    def create_assignment(self, payload: TrainingAssignmentCreate) -> TrainingAssignment:
        """Create a new training assignment."""
        now = datetime.now(timezone.utc)
        assignment_id = f"ASSIGN-{uuid4().hex[:8].upper()}"

        course = self._courses.get(payload.course_id)
        if course is None:
            raise ValueError(f"Course '{payload.course_id}' not found")

        assignment = TrainingAssignment(
            id=assignment_id,
            course_id=payload.course_id,
            user_id=payload.user_id,
            user_name=payload.user_name,
            role=payload.role,
            site_id=payload.site_id,
            assigned_date=now,
            due_date=payload.due_date,
            completion_date=None,
            status=CompletionStatus.NOT_STARTED,
            score=None,
            attempts=0,
            certificate_id=None,
        )
        with self._lock:
            self._assignments[assignment_id] = assignment
        logger.info(
            "Created training assignment %s: user=%s course=%s",
            assignment_id, payload.user_id, payload.course_id,
        )
        return assignment

    def update_assignment(
        self, assignment_id: str, payload: TrainingAssignmentUpdate
    ) -> TrainingAssignment | None:
        """Update a training assignment."""
        with self._lock:
            existing = self._assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TrainingAssignment(**data)
            self._assignments[assignment_id] = updated
        return updated

    def complete_assignment(
        self, assignment_id: str, payload: TrainingAssignmentComplete
    ) -> TrainingAssignment | None:
        """Complete a training assignment with a score."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._assignments.get(assignment_id)
            if existing is None:
                return None

            if existing.status == CompletionStatus.COMPLETED:
                raise ValueError(f"Assignment '{assignment_id}' is already completed")

            course = self._courses.get(existing.course_id)
            passed = course is not None and payload.score >= course.passing_score

            data = existing.model_dump()
            data["score"] = payload.score
            data["completion_date"] = payload.completion_date or now
            data["attempts"] = existing.attempts + 1
            data["status"] = CompletionStatus.COMPLETED if passed else CompletionStatus.IN_PROGRESS

            if passed:
                data["certificate_id"] = f"CERT-{uuid4().hex[:8].upper()}"

            updated = TrainingAssignment(**data)
            self._assignments[assignment_id] = updated

        logger.info(
            "Completed assignment %s: score=%.1f passed=%s",
            assignment_id, payload.score, passed,
        )
        return updated

    def delete_assignment(self, assignment_id: str) -> bool:
        """Delete a training assignment. Returns True if deleted."""
        with self._lock:
            if assignment_id in self._assignments:
                del self._assignments[assignment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Competency Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        user_id: str | None = None,
        skill_area: str | None = None,
        level: CompetencyLevel | None = None,
    ) -> list[CompetencyAssessment]:
        """List competency assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if user_id is not None:
            result = [a for a in result if a.user_id == user_id]
        if skill_area is not None:
            result = [a for a in result if skill_area.lower() in a.skill_area.lower()]
        if level is not None:
            result = [a for a in result if a.current_level == level]

        return sorted(result, key=lambda a: a.assessed_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> CompetencyAssessment | None:
        """Get a single assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: CompetencyAssessmentCreate) -> CompetencyAssessment:
        """Create a new competency assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"COMP-{uuid4().hex[:8].upper()}"
        assessment = CompetencyAssessment(
            id=assessment_id,
            user_id=payload.user_id,
            skill_area=payload.skill_area,
            current_level=payload.current_level,
            assessed_date=now,
            assessor=payload.assessor,
            next_assessment_date=payload.next_assessment_date,
            evidence=payload.evidence,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info(
            "Created competency assessment %s: user=%s skill=%s level=%s",
            assessment_id, payload.user_id, payload.skill_area, payload.current_level.value,
        )
        return assessment

    def update_assessment(
        self, assessment_id: str, payload: CompetencyAssessmentUpdate
    ) -> CompetencyAssessment | None:
        """Update a competency assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CompetencyAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete a competency assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Training Matrix
    # ------------------------------------------------------------------

    def list_training_matrix(self) -> list[TrainingMatrix]:
        """List training matrix for all roles."""
        with self._lock:
            result = list(self._matrix.values())
        return sorted(result, key=lambda m: m.role)

    def get_training_matrix(self, role: str) -> TrainingMatrix | None:
        """Get training matrix for a specific role."""
        with self._lock:
            return self._matrix.get(role)

    # ------------------------------------------------------------------
    # Auto-Assignment
    # ------------------------------------------------------------------

    def auto_assign(self, payload: AutoAssignRequest) -> AutoAssignResponse:
        """Auto-assign training courses based on user role and training matrix."""
        now = datetime.now(timezone.utc)
        matrix_entry = self._matrix.get(payload.role)
        if matrix_entry is None:
            raise ValueError(f"No training matrix found for role '{payload.role}'")

        # Get existing assignments for this user
        with self._lock:
            existing_course_ids = {
                a.course_id for a in self._assignments.values()
                if a.user_id == payload.user_id
                and a.status not in (CompletionStatus.EXPIRED,)
            }

        created: list[TrainingAssignment] = []
        for course_id in matrix_entry.required_courses:
            if course_id in existing_course_ids:
                continue

            course = self._courses.get(course_id)
            if course is None:
                continue

            assignment_id = f"ASSIGN-{uuid4().hex[:8].upper()}"
            assignment = TrainingAssignment(
                id=assignment_id,
                course_id=course_id,
                user_id=payload.user_id,
                user_name=payload.user_name,
                role=payload.role,
                site_id=payload.site_id,
                assigned_date=now,
                due_date=now + timedelta(days=30),
                completion_date=None,
                status=CompletionStatus.NOT_STARTED,
                score=None,
                attempts=0,
                certificate_id=None,
            )
            with self._lock:
                self._assignments[assignment_id] = assignment
            created.append(assignment)

        logger.info(
            "Auto-assigned %d courses for user %s (role=%s)",
            len(created), payload.user_id, payload.role,
        )
        return AutoAssignResponse(
            assignments_created=len(created),
            assignments=created,
        )

    # ------------------------------------------------------------------
    # Expiry Tracking
    # ------------------------------------------------------------------

    def get_expiring_certifications(
        self, days: int = EXPIRY_WARNING_DAYS
    ) -> list[CertificationExpiryAlert]:
        """Get certifications expiring within the specified number of days."""
        now = datetime.now(timezone.utc)
        alerts: list[CertificationExpiryAlert] = []

        with self._lock:
            assignments = list(self._assignments.values())

        for a in assignments:
            if a.status != CompletionStatus.COMPLETED or a.completion_date is None:
                continue

            course = self._courses.get(a.course_id)
            if course is None or course.expiry_months == 0:
                continue

            expiry_date = a.completion_date + timedelta(days=course.expiry_months * 30)
            days_until = (expiry_date - now).days

            if 0 < days_until <= days:
                alerts.append(CertificationExpiryAlert(
                    assignment_id=a.id,
                    user_id=a.user_id,
                    user_name=a.user_name,
                    course_id=a.course_id,
                    course_title=course.title,
                    completion_date=a.completion_date,
                    expiry_date=expiry_date,
                    days_until_expiry=days_until,
                ))

        return sorted(alerts, key=lambda x: x.days_until_expiry)

    def get_recertification_reminders(self) -> list[RecertificationReminder]:
        """Get re-certification reminders for expiring training."""
        now = datetime.now(timezone.utc)
        reminders: list[RecertificationReminder] = []

        with self._lock:
            assignments = list(self._assignments.values())

        for a in assignments:
            if a.status != CompletionStatus.COMPLETED or a.completion_date is None:
                continue

            course = self._courses.get(a.course_id)
            if course is None or course.expiry_months == 0:
                continue

            expiry_date = a.completion_date + timedelta(days=course.expiry_months * 30)
            days_until = (expiry_date - now).days

            if days_until <= 90:
                if days_until <= 7:
                    priority = "urgent"
                elif days_until <= 30:
                    priority = "warning"
                else:
                    priority = "info"

                reminders.append(RecertificationReminder(
                    user_id=a.user_id,
                    user_name=a.user_name,
                    course_id=a.course_id,
                    course_title=course.title,
                    expiry_date=expiry_date,
                    days_until_expiry=days_until,
                    priority=priority,
                ))

        return sorted(reminders, key=lambda x: x.days_until_expiry)

    # ------------------------------------------------------------------
    # Overdue Detection
    # ------------------------------------------------------------------

    def get_overdue_assignments(self) -> list[TrainingAssignment]:
        """Get assignments that are past their due date and not completed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = [
                a for a in self._assignments.values()
                if a.status in (CompletionStatus.NOT_STARTED, CompletionStatus.IN_PROGRESS)
                and a.due_date < now
            ]
        return sorted(result, key=lambda a: a.due_date)

    # ------------------------------------------------------------------
    # Compliance Calculation
    # ------------------------------------------------------------------

    def calculate_compliance_by_role(self) -> dict[str, float]:
        """Calculate training compliance rate per role."""
        with self._lock:
            assignments = list(self._assignments.values())

        role_totals: dict[str, int] = {}
        role_completed: dict[str, int] = {}

        for a in assignments:
            role_totals[a.role] = role_totals.get(a.role, 0) + 1
            if a.status in (CompletionStatus.COMPLETED, CompletionStatus.WAIVED):
                role_completed[a.role] = role_completed.get(a.role, 0) + 1

        result: dict[str, float] = {}
        for role, total in role_totals.items():
            completed = role_completed.get(role, 0)
            result[role] = round(completed / max(1, total) * 100, 1)

        return result

    def calculate_compliance_by_site(self) -> dict[str, float]:
        """Calculate training compliance rate per site."""
        with self._lock:
            assignments = list(self._assignments.values())

        site_totals: dict[str, int] = {}
        site_completed: dict[str, int] = {}

        for a in assignments:
            site_totals[a.site_id] = site_totals.get(a.site_id, 0) + 1
            if a.status in (CompletionStatus.COMPLETED, CompletionStatus.WAIVED):
                site_completed[a.site_id] = site_completed.get(a.site_id, 0) + 1

        result: dict[str, float] = {}
        for site_id, total in site_totals.items():
            completed = site_completed.get(site_id, 0)
            result[site_id] = round(completed / max(1, total) * 100, 1)

        return result

    # ------------------------------------------------------------------
    # Competency Gap Analysis
    # ------------------------------------------------------------------

    def get_competency_gap_analysis(self, user_id: str) -> CompetencyGapAnalysis | None:
        """Perform competency gap analysis for a user."""
        # Find user info from assignments
        with self._lock:
            user_assignments = [
                a for a in self._assignments.values()
                if a.user_id == user_id
            ]
            user_assessments = [
                a for a in self._assessments.values()
                if a.user_id == user_id
            ]

        if not user_assignments:
            return None

        role = user_assignments[0].role

        # Identify gaps
        gaps: list[str] = []
        recommendations: list[str] = []

        # Check incomplete required training
        matrix_entry = self._matrix.get(role)
        if matrix_entry:
            completed_courses = {
                a.course_id for a in user_assignments
                if a.status == CompletionStatus.COMPLETED
            }
            for course_id in matrix_entry.required_courses:
                if course_id not in completed_courses:
                    course = self._courses.get(course_id)
                    if course:
                        gaps.append(f"Required training incomplete: {course.title}")
                        recommendations.append(f"Complete {course.title} (Course ID: {course_id})")

        # Check competency levels below proficient
        for assessment in user_assessments:
            if assessment.current_level in (CompetencyLevel.NOVICE, CompetencyLevel.COMPETENT):
                gaps.append(
                    f"Below proficient in {assessment.skill_area} "
                    f"(current: {assessment.current_level.value})"
                )
                recommendations.append(
                    f"Additional training/mentoring in {assessment.skill_area}"
                )

        # Calculate overall score
        if user_assessments:
            total_score = sum(
                COMPETENCY_SCORES[a.current_level] for a in user_assessments
            )
            overall_score = round(total_score / len(user_assessments), 1)
        else:
            overall_score = 0.0

        return CompetencyGapAnalysis(
            user_id=user_id,
            role=role,
            gaps=gaps,
            recommendations=recommendations,
            overall_competency_score=overall_score,
        )

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> TrainingMetrics:
        """Compute aggregated training & competency metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            courses = list(self._courses.values())
            assignments = list(self._assignments.values())

        # Completion rate
        total = len(assignments)
        completed = sum(
            1 for a in assignments
            if a.status in (CompletionStatus.COMPLETED, CompletionStatus.WAIVED)
        )
        completion_rate = round(completed / max(1, total) * 100, 1)

        # Overdue
        overdue_count = sum(
            1 for a in assignments
            if a.status in (CompletionStatus.NOT_STARTED, CompletionStatus.IN_PROGRESS)
            and a.due_date < now
        )

        # Average score
        scores = [a.score for a in assignments if a.score is not None]
        avg_score = round(sum(scores) / max(1, len(scores)), 1) if scores else 0.0

        # Expiring certifications
        expiring = self.get_expiring_certifications(days=30)

        # Compliance by role and site
        compliance_by_role = self.calculate_compliance_by_role()
        compliance_by_site = self.calculate_compliance_by_site()

        return TrainingMetrics(
            total_courses=len(courses),
            total_assignments=total,
            completion_rate=completion_rate,
            overdue_count=overdue_count,
            avg_score=avg_score,
            certifications_expiring_30d=len(expiring),
            compliance_by_role=compliance_by_role,
            compliance_by_site=compliance_by_site,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TrainingManagementService | None = None
_instance_lock = threading.Lock()


def get_training_service() -> TrainingManagementService:
    """Return the singleton TrainingManagementService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrainingManagementService()
    return _instance


def reset_training_service() -> TrainingManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = TrainingManagementService()
    return _instance
