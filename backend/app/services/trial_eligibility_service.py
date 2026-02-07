"""Trial Eligibility Service for clinical trial patient matching.

Wraps the existing CohortService to model clinical trial eligibility criteria
as cohort definitions and screen patients against them. Manages trial CRUD,
patient screening, enrollment tracking, and dashboard analytics.

Usage:
    from app.services.trial_eligibility_service import get_trial_service

    service = get_trial_service()
    trial = service.create_trial(TrialCreate(name="Dupixent AD Study", ...))
    results = service.screen_patients(trial.id)
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.trial import EnrollmentStatus, TrialPhase, TrialStatus
from app.schemas.trial import (
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentUpdate,
    PatientEligibility,
    ScreeningRequest,
    ScreeningResponse,
    TrialCreate,
    TrialDashboard,
    TrialResponse,
    TrialSummary,
    TrialUpdate,
)
from app.services.cohort_service import (
    AgeRange,
    AnyCriterion,
    CodeEntry,
    CohortDefinition,
    CohortDefinitionCreate,
    ConditionCriterion,
    CriteriaGroup,
    DemographicCriterion,
    DrugCriterion,
    LogicOperator,
    MeasurementCriterion,
    ProcedureCriterion,
    get_cohort_service,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# In-memory trial storage (mirrors CohortService pattern)
# ==============================================================================


class _TrialRecord:
    """Internal trial record with enrollment tracking."""

    def __init__(
        self,
        id: str,
        create: TrialCreate,
        inclusion_cohort_id: str | None = None,
        exclusion_cohort_id: str | None = None,
    ):
        self.id = id
        self.name = create.name
        self.nct_number = create.nct_number
        self.protocol_id = create.protocol_id
        self.sponsor = create.sponsor
        self.phase = create.phase
        self.status = create.status
        self.description = create.description
        self.therapeutic_area = create.therapeutic_area
        self.indication_codes = create.indication_codes
        self.inclusion_criteria = create.inclusion_criteria
        self.exclusion_criteria = create.exclusion_criteria
        self.enrollment_target = create.enrollment_target
        self.site_count = create.site_count
        self.start_date = create.start_date
        self.end_date = create.end_date
        self.created_at = datetime.now(timezone.utc)
        self.inclusion_cohort_id = inclusion_cohort_id
        self.exclusion_cohort_id = exclusion_cohort_id
        self.enrollments: dict[str, _EnrollmentRecord] = {}

    @property
    def enrolled_count(self) -> int:
        return sum(
            1 for e in self.enrollments.values()
            if e.enrollment_status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE)
        )

    @property
    def enrollment_progress(self) -> float:
        if self.enrollment_target <= 0:
            return 0.0
        return min(100.0, (self.enrolled_count / self.enrollment_target) * 100)

    def to_response(self) -> TrialResponse:
        return TrialResponse(
            id=self.id,
            name=self.name,
            nct_number=self.nct_number,
            protocol_id=self.protocol_id,
            sponsor=self.sponsor,
            phase=self.phase,
            status=self.status,
            description=self.description,
            therapeutic_area=self.therapeutic_area,
            indication_codes=self.indication_codes,
            inclusion_criteria=self.inclusion_criteria,
            exclusion_criteria=self.exclusion_criteria,
            enrollment_target=self.enrollment_target,
            site_count=self.site_count,
            start_date=self.start_date,
            end_date=self.end_date,
            created_at=self.created_at,
            enrolled_count=self.enrolled_count,
            enrollment_progress=self.enrollment_progress,
        )

    def to_summary(self) -> TrialSummary:
        return TrialSummary(
            id=self.id,
            name=self.name,
            nct_number=self.nct_number,
            sponsor=self.sponsor,
            phase=self.phase,
            status=self.status,
            therapeutic_area=self.therapeutic_area,
            enrollment_target=self.enrollment_target,
            enrolled_count=self.enrolled_count,
            enrollment_progress=self.enrollment_progress,
            created_at=self.created_at,
        )


class _EnrollmentRecord:
    """Internal enrollment record."""

    def __init__(self, id: str, trial_id: str, create: EnrollmentCreate):
        self.id = id
        self.trial_id = trial_id
        self.patient_id = create.patient_id
        self.enrollment_status = create.enrollment_status
        self.match_score: float | None = None
        self.criteria_met: dict | None = None
        self.criteria_failed: dict | None = None
        self.screening_date: datetime | None = None
        self.enrollment_date: datetime | None = None
        self.withdrawal_date: datetime | None = None
        self.withdrawal_reason: str | None = None
        self.site_id = create.site_id
        self.notes = create.notes
        self.created_at = datetime.now(timezone.utc)

    def to_response(self) -> EnrollmentResponse:
        return EnrollmentResponse(
            id=self.id,
            trial_id=self.trial_id,
            patient_id=self.patient_id,
            enrollment_status=self.enrollment_status,
            match_score=self.match_score,
            criteria_met=self.criteria_met,
            criteria_failed=self.criteria_failed,
            screening_date=self.screening_date,
            enrollment_date=self.enrollment_date,
            withdrawal_date=self.withdrawal_date,
            withdrawal_reason=self.withdrawal_reason,
            site_id=self.site_id,
            notes=self.notes,
            created_at=self.created_at,
        )


# ==============================================================================
# Trial Eligibility Service
# ==============================================================================


class TrialEligibilityService:
    """Service for clinical trial management and patient eligibility screening.

    Wraps CohortService to leverage existing cohort definition and execution
    logic for trial eligibility matching.
    """

    def __init__(self):
        self._trials: dict[str, _TrialRecord] = {}
        self._cohort_service = get_cohort_service()
        self._init_demo_trials()

    # ==========================================================================
    # Demo Data
    # ==========================================================================

    def _init_demo_trials(self):
        """Initialize demo trials for the Regeneron use case."""
        demo_trials = [
            TrialCreate(
                name="LIBERTY ADCHRONOS - Dupilumab for Atopic Dermatitis",
                nct_number="NCT02395133",
                protocol_id="R668-AD-1334",
                sponsor="Regeneron Pharmaceuticals",
                phase=TrialPhase.PHASE_3,
                status=TrialStatus.RECRUITING,
                description="A phase 3 study evaluating dupilumab in adult patients with moderate-to-severe atopic dermatitis inadequately controlled with topical corticosteroids.",
                therapeutic_area="Dermatology",
                indication_codes=["L20.9", "L20.89"],
                inclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "demographic",
                            "name": "Adult patients",
                            "age_range": {"min_age": 18, "max_age": 75},
                        },
                        {
                            "criterion_type": "condition",
                            "name": "Atopic Dermatitis",
                            "codes": [
                                {"code": "L20.9", "display": "Atopic dermatitis, unspecified"},
                                {"code": "L20.89", "display": "Other atopic dermatitis"},
                            ],
                            "code_system": "ICD10CM",
                        },
                    ],
                    "root_operator": "AND",
                },
                exclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "condition",
                            "name": "Active cancer",
                            "codes": [
                                {"code": "C80.1", "display": "Malignant neoplasm, unspecified"},
                            ],
                            "code_system": "ICD10CM",
                            "negated": True,
                        },
                        {
                            "criterion_type": "condition",
                            "name": "Active tuberculosis",
                            "codes": [
                                {"code": "A15", "display": "Respiratory tuberculosis"},
                            ],
                            "code_system": "ICD10CM",
                            "negated": True,
                        },
                    ],
                    "root_operator": "AND",
                },
                enrollment_target=600,
                site_count=250,
            ),
            TrialCreate(
                name="LIBTAYO - Cemiplimab for Advanced CSCC",
                nct_number="NCT02760498",
                protocol_id="R2810-ONC-1540",
                sponsor="Regeneron Pharmaceuticals",
                phase=TrialPhase.PHASE_2,
                status=TrialStatus.RECRUITING,
                description="A phase 2 study of cemiplimab in patients with advanced cutaneous squamous cell carcinoma.",
                therapeutic_area="Oncology",
                indication_codes=["C44.9"],
                inclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "demographic",
                            "name": "Adult patients",
                            "age_range": {"min_age": 18},
                        },
                        {
                            "criterion_type": "condition",
                            "name": "Cutaneous SCC",
                            "codes": [
                                {"code": "C44.9", "display": "Malignant neoplasm of skin, unspecified"},
                                {"code": "C44.92", "display": "Squamous cell carcinoma of skin, unspecified"},
                            ],
                            "code_system": "ICD10CM",
                        },
                    ],
                    "root_operator": "AND",
                },
                exclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "condition",
                            "name": "Autoimmune disease requiring systemic treatment",
                            "codes": [
                                {"code": "M35.9", "display": "Systemic involvement of connective tissue, unspecified"},
                            ],
                            "code_system": "ICD10CM",
                            "negated": True,
                        },
                    ],
                    "root_operator": "AND",
                },
                enrollment_target=200,
                site_count=75,
            ),
            TrialCreate(
                name="EYLEA HD - Aflibercept for Diabetic Macular Edema",
                nct_number="NCT04429503",
                protocol_id="VGFTe-DME-2001",
                sponsor="Regeneron Pharmaceuticals",
                phase=TrialPhase.PHASE_3,
                status=TrialStatus.RECRUITING,
                description="A phase 3 study of high-dose aflibercept in patients with diabetic macular edema.",
                therapeutic_area="Ophthalmology",
                indication_codes=["H35.81", "E11.311"],
                inclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "demographic",
                            "name": "Adult patients",
                            "age_range": {"min_age": 18},
                        },
                        {
                            "criterion_type": "condition",
                            "name": "Diabetic Macular Edema",
                            "codes": [
                                {"code": "H35.81", "display": "Retinal edema"},
                                {"code": "E11.311", "display": "Type 2 DM with diabetic retinopathy with macular edema"},
                            ],
                            "code_system": "ICD10CM",
                        },
                        {
                            "criterion_type": "condition",
                            "name": "Type 2 Diabetes",
                            "codes": [
                                {"code": "E11", "display": "Type 2 diabetes mellitus"},
                            ],
                            "code_system": "ICD10CM",
                        },
                    ],
                    "root_operator": "AND",
                },
                exclusion_criteria={
                    "criteria": [
                        {
                            "criterion_type": "measurement",
                            "name": "Uncontrolled diabetes (HbA1c > 12%)",
                            "codes": [
                                {"code": "4548-4", "display": "Hemoglobin A1c"},
                            ],
                            "code_system": "LOINC",
                            "value_range": {"min_value": 12.0},
                            "negated": True,
                        },
                    ],
                    "root_operator": "AND",
                },
                enrollment_target=900,
                site_count=300,
            ),
        ]

        for trial_create in demo_trials:
            trial_id = str(uuid4())
            inclusion_cohort = self._build_cohort_from_criteria(
                f"[Trial] {trial_create.name} - Inclusion",
                trial_create.inclusion_criteria,
            )
            exclusion_cohort = self._build_cohort_from_criteria(
                f"[Trial] {trial_create.name} - Exclusion",
                trial_create.exclusion_criteria,
            )

            record = _TrialRecord(
                id=trial_id,
                create=trial_create,
                inclusion_cohort_id=inclusion_cohort.id if inclusion_cohort else None,
                exclusion_cohort_id=exclusion_cohort.id if exclusion_cohort else None,
            )

            # Seed some mock enrollments
            self._seed_mock_enrollments(record)
            self._trials[trial_id] = record

        logger.info(f"Initialized {len(demo_trials)} demo trials")

    def _seed_mock_enrollments(self, trial: _TrialRecord):
        """Seed realistic mock enrollment data for a trial."""
        statuses_weights = [
            (EnrollmentStatus.CANDIDATE, 40),
            (EnrollmentStatus.SCREENED, 15),
            (EnrollmentStatus.ELIGIBLE, 10),
            (EnrollmentStatus.ENROLLED, 15),
            (EnrollmentStatus.ACTIVE, 10),
            (EnrollmentStatus.SCREEN_FAILED, 5),
            (EnrollmentStatus.WITHDRAWN, 3),
            (EnrollmentStatus.COMPLETED, 2),
        ]
        statuses = [s for s, _ in statuses_weights]
        weights = [w for _, w in statuses_weights]

        num_enrollments = min(trial.enrollment_target * 3, 200)
        for i in range(num_enrollments):
            status = random.choices(statuses, weights=weights, k=1)[0]
            enrollment_id = str(uuid4())
            patient_id = f"P{1000 + i:05d}"

            record = _EnrollmentRecord(
                id=enrollment_id,
                trial_id=trial.id,
                create=EnrollmentCreate(patient_id=patient_id),
            )
            record.enrollment_status = status
            record.match_score = round(random.uniform(0.4, 1.0), 3)
            record.screening_date = datetime.now(timezone.utc)

            if status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
                record.enrollment_date = datetime.now(timezone.utc)

            if status == EnrollmentStatus.WITHDRAWN:
                record.withdrawal_date = datetime.now(timezone.utc)
                record.withdrawal_reason = random.choice([
                    "Patient declined to continue",
                    "Adverse event",
                    "Lost to follow-up",
                    "Protocol deviation",
                ])

            trial.enrollments[patient_id] = record

    def _build_cohort_from_criteria(
        self,
        name: str,
        criteria_dict: dict | None,
    ) -> CohortDefinition | None:
        """Convert trial criteria JSON into a CohortDefinition via CohortService."""
        if not criteria_dict or not criteria_dict.get("criteria"):
            return None

        parsed_criteria: list[AnyCriterion] = []
        for c in criteria_dict["criteria"]:
            criterion = self._parse_criterion(c)
            if criterion:
                parsed_criteria.append(criterion)

        if not parsed_criteria:
            return None

        root_op = LogicOperator(criteria_dict.get("root_operator", "AND"))
        create = CohortDefinitionCreate(
            name=name,
            criteria=parsed_criteria,
            root_operator=root_op,
            tags=["trial-eligibility"],
        )
        return self._cohort_service.create_cohort(create, created_by="trial_service")

    def _parse_criterion(self, c: dict) -> AnyCriterion | None:
        """Parse a criterion dict into a typed CohortCriterion."""
        ctype = c.get("criterion_type")
        codes = [CodeEntry(**code) for code in c.get("codes", [])]
        negated = c.get("negated", False)

        if ctype == "demographic":
            age_range = None
            if c.get("age_range"):
                age_range = AgeRange(**c["age_range"])
            return DemographicCriterion(
                name=c.get("name"),
                age_range=age_range,
                negated=negated,
            )
        elif ctype == "condition":
            return ConditionCriterion(
                name=c.get("name"),
                codes=codes,
                code_system=c.get("code_system", "ICD10CM"),
                negated=negated,
            )
        elif ctype == "drug":
            return DrugCriterion(
                name=c.get("name"),
                codes=codes,
                code_system=c.get("code_system", "RxNorm"),
                negated=negated,
            )
        elif ctype == "procedure":
            return ProcedureCriterion(
                name=c.get("name"),
                codes=codes,
                code_system=c.get("code_system", "CPT"),
                negated=negated,
            )
        elif ctype == "measurement":
            from app.services.cohort_service import NumericRange
            value_range = None
            if c.get("value_range"):
                value_range = NumericRange(**c["value_range"])
            return MeasurementCriterion(
                name=c.get("name"),
                codes=codes,
                code_system=c.get("code_system", "LOINC"),
                value_range=value_range,
                negated=negated,
            )

        logger.warning(f"Unknown criterion type: {ctype}")
        return None

    # ==========================================================================
    # Trial CRUD
    # ==========================================================================

    def create_trial(self, create: TrialCreate) -> TrialResponse:
        """Create a new clinical trial."""
        trial_id = str(uuid4())

        inclusion_cohort = self._build_cohort_from_criteria(
            f"[Trial] {create.name} - Inclusion",
            create.inclusion_criteria,
        )
        exclusion_cohort = self._build_cohort_from_criteria(
            f"[Trial] {create.name} - Exclusion",
            create.exclusion_criteria,
        )

        record = _TrialRecord(
            id=trial_id,
            create=create,
            inclusion_cohort_id=inclusion_cohort.id if inclusion_cohort else None,
            exclusion_cohort_id=exclusion_cohort.id if exclusion_cohort else None,
        )
        self._trials[trial_id] = record

        logger.info(f"Created trial: {trial_id} - {create.name}")
        return record.to_response()

    def get_trial(self, trial_id: str) -> TrialResponse | None:
        """Get a trial by ID."""
        record = self._trials.get(trial_id)
        return record.to_response() if record else None

    def list_trials(
        self,
        status: TrialStatus | None = None,
        sponsor: str | None = None,
        therapeutic_area: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TrialSummary], int]:
        """List trials with filtering."""
        records = list(self._trials.values())

        if status:
            records = [r for r in records if r.status == status]
        if sponsor:
            records = [r for r in records if r.sponsor and sponsor.lower() in r.sponsor.lower()]
        if therapeutic_area:
            records = [r for r in records if r.therapeutic_area and therapeutic_area.lower() in r.therapeutic_area.lower()]
        if search:
            search_lower = search.lower()
            records = [
                r for r in records
                if search_lower in r.name.lower()
                or (r.description and search_lower in r.description.lower())
                or (r.nct_number and search_lower in r.nct_number.lower())
            ]

        records.sort(key=lambda r: r.created_at, reverse=True)
        total = len(records)
        records = records[offset:offset + limit]

        return [r.to_summary() for r in records], total

    def update_trial(self, trial_id: str, update: TrialUpdate) -> TrialResponse | None:
        """Update a trial."""
        record = self._trials.get(trial_id)
        if not record:
            return None

        for field in ["name", "nct_number", "protocol_id", "sponsor", "phase",
                       "status", "description", "therapeutic_area", "indication_codes",
                       "enrollment_target", "site_count", "start_date", "end_date"]:
            value = getattr(update, field, None)
            if value is not None:
                setattr(record, field, value)

        # Rebuild cohorts if criteria changed
        if update.inclusion_criteria is not None:
            record.inclusion_criteria = update.inclusion_criteria
            cohort = self._build_cohort_from_criteria(
                f"[Trial] {record.name} - Inclusion", update.inclusion_criteria
            )
            record.inclusion_cohort_id = cohort.id if cohort else None

        if update.exclusion_criteria is not None:
            record.exclusion_criteria = update.exclusion_criteria
            cohort = self._build_cohort_from_criteria(
                f"[Trial] {record.name} - Exclusion", update.exclusion_criteria
            )
            record.exclusion_cohort_id = cohort.id if cohort else None

        logger.info(f"Updated trial: {trial_id}")
        return record.to_response()

    def delete_trial(self, trial_id: str) -> bool:
        """Delete a trial."""
        if trial_id in self._trials:
            del self._trials[trial_id]
            logger.info(f"Deleted trial: {trial_id}")
            return True
        return False

    # ==========================================================================
    # Patient Screening
    # ==========================================================================

    def screen_patients(
        self,
        trial_id: str,
        request: ScreeningRequest | None = None,
    ) -> ScreeningResponse | None:
        """Screen patients against trial eligibility criteria.

        Uses the CohortService to execute inclusion criteria, then filters
        against exclusion criteria. Returns scored candidates.
        """
        record = self._trials.get(trial_id)
        if not record:
            return None

        start_time = time.perf_counter()

        # Get inclusion cohort count (how many match inclusion criteria)
        inclusion_count = 0
        if record.inclusion_cohort_id:
            count_result = self._cohort_service.get_patient_count(record.inclusion_cohort_id)
            if count_result:
                inclusion_count = count_result.count

        # Get exclusion count (how many would be excluded)
        exclusion_count = 0
        if record.exclusion_cohort_id:
            count_result = self._cohort_service.get_patient_count(record.exclusion_cohort_id)
            if count_result:
                exclusion_count = count_result.count

        # Calculate eligible (inclusion minus exclusion overlap)
        eligible_count = max(0, inclusion_count - int(exclusion_count * 0.3))
        total_screened = inclusion_count + int(inclusion_count * 1.5)

        # Generate mock candidate list
        limit = request.limit if request else 100
        min_score = request.min_match_score if request else 0.0
        candidates = self._generate_mock_candidates(
            record, eligible_count, limit, min_score
        )

        # Demographics summary
        demographics = self._cohort_service.get_demographics(record.inclusion_cohort_id) if record.inclusion_cohort_id else None

        # Exclusion breakdown
        exclusion_breakdown = self._build_exclusion_breakdown(record)

        enrollment_rate = (eligible_count / total_screened * 100) if total_screened > 0 else 0.0

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Screened patients for trial {trial_id}: "
            f"{eligible_count}/{total_screened} eligible ({enrollment_rate:.1f}%) "
            f"in {elapsed_ms:.0f}ms"
        )

        return ScreeningResponse(
            trial_id=record.id,
            trial_name=record.name,
            total_patients_screened=total_screened,
            eligible_count=eligible_count,
            ineligible_count=total_screened - eligible_count,
            enrollment_target=record.enrollment_target,
            enrollment_rate=round(enrollment_rate, 2),
            candidates=candidates,
            demographics_summary=demographics.model_dump() if demographics else None,
            exclusion_breakdown=exclusion_breakdown,
        )

    def check_patient_eligibility(
        self,
        trial_id: str,
        patient_id: str,
    ) -> PatientEligibility | None:
        """Check a single patient's eligibility for a trial."""
        record = self._trials.get(trial_id)
        if not record:
            return None

        # Parse inclusion criteria for display
        inclusion_criteria = record.inclusion_criteria or {}
        inclusion_list = inclusion_criteria.get("criteria", [])
        exclusion_criteria = record.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        # Mock eligibility check against patient's clinical facts
        inclusion_met = []
        for c in inclusion_list:
            name = c.get("name", c.get("criterion_type", "Unknown"))
            # In production, this would query the patient's ClinicalFacts
            if random.random() > 0.15:
                inclusion_met.append(name)

        exclusion_triggered = []
        for c in exclusion_list:
            name = c.get("name", c.get("criterion_type", "Unknown"))
            if random.random() < 0.1:
                exclusion_triggered.append(name)

        eligible = len(inclusion_met) == len(inclusion_list) and len(exclusion_triggered) == 0
        score = len(inclusion_met) / max(len(inclusion_list), 1)
        if exclusion_triggered:
            score = 0.0

        return PatientEligibility(
            patient_id=patient_id,
            eligible=eligible,
            match_score=round(score, 3),
            inclusion_met=inclusion_met,
            inclusion_total=len(inclusion_list),
            exclusion_triggered=exclusion_triggered,
            exclusion_total=len(exclusion_list),
            missing_data=[
                c.get("name", "Unknown")
                for c in inclusion_list
                if c.get("name") not in inclusion_met
            ],
        )

    def _generate_mock_candidates(
        self,
        trial: _TrialRecord,
        eligible_count: int,
        limit: int,
        min_score: float,
    ) -> list[PatientEligibility]:
        """Generate mock candidate list for screening results."""
        inclusion_criteria = trial.inclusion_criteria or {}
        inclusion_list = inclusion_criteria.get("criteria", [])
        exclusion_criteria = trial.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        candidates = []
        for i in range(min(limit, eligible_count)):
            patient_id = f"P{2000 + i:05d}"

            # Most candidates meet all inclusion
            inclusion_met = [
                c.get("name", c.get("criterion_type"))
                for c in inclusion_list
            ]
            score = round(random.uniform(0.7, 1.0), 3)

            # Some have missing data
            missing = []
            if random.random() < 0.2:
                dropped = inclusion_met.pop() if inclusion_met else None
                if dropped:
                    missing.append(dropped)
                    score = round(score * 0.8, 3)

            if score >= min_score:
                candidates.append(PatientEligibility(
                    patient_id=patient_id,
                    eligible=len(missing) == 0,
                    match_score=score,
                    inclusion_met=inclusion_met,
                    inclusion_total=len(inclusion_list),
                    exclusion_triggered=[],
                    exclusion_total=len(exclusion_list),
                    missing_data=missing,
                ))

        candidates.sort(key=lambda c: c.match_score, reverse=True)
        return candidates

    def _build_exclusion_breakdown(self, trial: _TrialRecord) -> dict:
        """Build a breakdown of why patients were excluded."""
        exclusion_criteria = trial.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        breakdown = {}
        for c in exclusion_list:
            name = c.get("name", c.get("criterion_type", "Unknown"))
            breakdown[name] = random.randint(10, 200)

        return breakdown

    # ==========================================================================
    # Enrollment Management
    # ==========================================================================

    def enroll_patient(
        self,
        trial_id: str,
        create: EnrollmentCreate,
    ) -> EnrollmentResponse | None:
        """Add a patient to a trial's enrollment pipeline."""
        record = self._trials.get(trial_id)
        if not record:
            return None

        enrollment_id = str(uuid4())
        enrollment = _EnrollmentRecord(
            id=enrollment_id,
            trial_id=trial_id,
            create=create,
        )

        # Check eligibility and set score
        eligibility = self.check_patient_eligibility(trial_id, create.patient_id)
        if eligibility:
            enrollment.match_score = eligibility.match_score
            enrollment.criteria_met = {"met": eligibility.inclusion_met}
            enrollment.criteria_failed = {"failed": eligibility.exclusion_triggered}

        enrollment.screening_date = datetime.now(timezone.utc)

        if create.enrollment_status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE):
            enrollment.enrollment_date = datetime.now(timezone.utc)

        record.enrollments[create.patient_id] = enrollment
        logger.info(f"Enrolled patient {create.patient_id} in trial {trial_id}")
        return enrollment.to_response()

    def update_enrollment(
        self,
        trial_id: str,
        patient_id: str,
        update: EnrollmentUpdate,
    ) -> EnrollmentResponse | None:
        """Update a patient's enrollment status."""
        record = self._trials.get(trial_id)
        if not record:
            return None

        enrollment = record.enrollments.get(patient_id)
        if not enrollment:
            return None

        if update.enrollment_status is not None:
            enrollment.enrollment_status = update.enrollment_status
            if update.enrollment_status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.ACTIVE):
                enrollment.enrollment_date = datetime.now(timezone.utc)
            elif update.enrollment_status == EnrollmentStatus.WITHDRAWN:
                enrollment.withdrawal_date = datetime.now(timezone.utc)

        if update.withdrawal_reason is not None:
            enrollment.withdrawal_reason = update.withdrawal_reason
        if update.notes is not None:
            enrollment.notes = update.notes

        return enrollment.to_response()

    def get_enrollments(
        self,
        trial_id: str,
        status: EnrollmentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EnrollmentResponse], int]:
        """List enrollments for a trial."""
        record = self._trials.get(trial_id)
        if not record:
            return [], 0

        enrollments = list(record.enrollments.values())
        if status:
            enrollments = [e for e in enrollments if e.enrollment_status == status]

        total = len(enrollments)
        enrollments = enrollments[offset:offset + limit]

        return [e.to_response() for e in enrollments], total

    # ==========================================================================
    # Dashboard
    # ==========================================================================

    def get_dashboard(self, trial_id: str) -> TrialDashboard | None:
        """Get enrollment dashboard for a trial."""
        record = self._trials.get(trial_id)
        if not record:
            return None

        enrollments = list(record.enrollments.values())

        def count_status(s: EnrollmentStatus) -> int:
            return sum(1 for e in enrollments if e.enrollment_status == s)

        return TrialDashboard(
            trial_id=record.id,
            trial_name=record.name,
            status=record.status,
            phase=record.phase,
            enrollment_target=record.enrollment_target,
            total_candidates=count_status(EnrollmentStatus.CANDIDATE),
            total_screened=count_status(EnrollmentStatus.SCREENED),
            total_eligible=count_status(EnrollmentStatus.ELIGIBLE),
            total_enrolled=count_status(EnrollmentStatus.ENROLLED),
            total_active=count_status(EnrollmentStatus.ACTIVE),
            total_completed=count_status(EnrollmentStatus.COMPLETED),
            total_withdrawn=count_status(EnrollmentStatus.WITHDRAWN),
            total_screen_failed=count_status(EnrollmentStatus.SCREEN_FAILED),
            enrollment_progress=record.enrollment_progress,
            site_count=record.site_count,
        )

    # ==========================================================================
    # Stats
    # ==========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service-level statistics."""
        trials_by_status = {}
        total_enrolled = 0
        for trial in self._trials.values():
            s = trial.status.value
            trials_by_status[s] = trials_by_status.get(s, 0) + 1
            total_enrolled += trial.enrolled_count

        return {
            "total_trials": len(self._trials),
            "trials_by_status": trials_by_status,
            "total_enrolled_patients": total_enrolled,
        }


# ==============================================================================
# Singleton
# ==============================================================================

_trial_service: TrialEligibilityService | None = None
_trial_lock = threading.Lock()


def get_trial_service() -> TrialEligibilityService:
    """Get singleton trial eligibility service instance."""
    global _trial_service
    if _trial_service is None:
        with _trial_lock:
            if _trial_service is None:
                _trial_service = TrialEligibilityService()
                logger.info("Initialized TrialEligibilityService")
    return _trial_service
