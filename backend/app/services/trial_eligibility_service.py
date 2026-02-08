"""Trial Eligibility Service for clinical trial patient matching.

Screens patients against eligibility criteria by querying the ClinicalFacts
table. Manages trial CRUD, patient screening, enrollment tracking, and
dashboard analytics.

Usage:
    from app.services.trial_eligibility_service import get_trial_service

    service = get_trial_service()
    trial = service.create_trial(TrialCreate(name="Dupixent AD Study", ...))
    results = await service.screen_patients(trial.id, session=session)
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, cast, or_, select, Float as SAFloat
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditAction, log_audit
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGNode
from app.models.trial import EnrollmentStatus, Trial, TrialEnrollment, TrialPhase, TrialStatus
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import NodeType
from app.schemas.trial import (
    CDS_DISCLAIMER,
    CriterionResult,
    DataCompletenessScore,
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

logger = logging.getLogger(__name__)

# Dedicated logger for patient-safety events.  These messages are emitted at
# WARNING level to ensure they surface in monitoring dashboards and log
# aggregation even when the default log level is INFO.
safety_logger = logging.getLogger("patient_safety")


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

    Queries the clinical_facts and kg_nodes tables directly for eligibility
    screening. Trial metadata is stored in-memory; patient screening uses
    real database queries.
    """

    def __init__(self):
        self._trials: dict[str, _TrialRecord] = {}
        self._loaded_from_db: bool = False
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
                                {"code": "C80", "display": "malignant"},
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

        # Stable UUIDs matching seed_demo_data.py so in-memory and DB IDs agree
        stable_ids = [
            "00000000-de00-0002-0000-000000000002",  # DUPIXENT (LIBERTY ADCHRONOS)
            "00000000-de00-0003-0000-000000000003",  # LIBTAYO
            "00000000-de00-0001-0000-000000000001",  # EYLEA HD
        ]

        for trial_create, trial_id in zip(demo_trials, stable_ids):
            record = _TrialRecord(
                id=trial_id,
                create=trial_create,
            )
            self._trials[trial_id] = record

        logger.info(f"Initialized {len(demo_trials)} demo trials")

    # ==========================================================================
    # DB Loading
    # ==========================================================================

    async def load_from_db(self, session: AsyncSession) -> None:
        """Load trials and enrollments from the database.

        If the DB has trial rows, clears the in-memory dict and replaces
        it with DB data so that IDs always match.
        """
        if self._loaded_from_db:
            return

        try:
            result = await session.execute(
                select(Trial).where(Trial.deleted_at.is_(None))
            )
            db_trials = result.scalars().all()

            if not db_trials:
                logger.info("No trials in DB; keeping in-memory demo trials")
                self._loaded_from_db = True
                return

            # Merge DB records with in-memory demo trials.
            # DB provides stable IDs and enrollment data; in-memory
            # provides eligibility criteria if the DB columns are NULL.
            existing_by_name: dict[str, _TrialRecord] = {
                r.name: r for r in self._trials.values()
            }
            merged: dict[str, _TrialRecord] = {}

            for t in db_trials:
                # Prefer DB criteria; fall back to in-memory demo criteria
                demo = existing_by_name.get(t.name)
                inc = t.inclusion_criteria or (demo.inclusion_criteria if demo else None)
                exc = t.exclusion_criteria or (demo.exclusion_criteria if demo else None)

                trial_create = TrialCreate(
                    name=t.name,
                    nct_number=t.nct_number,
                    protocol_id=t.protocol_id,
                    sponsor=t.sponsor,
                    phase=t.phase,
                    status=t.status,
                    description=t.description,
                    therapeutic_area=t.therapeutic_area,
                    indication_codes=t.indication_codes,
                    inclusion_criteria=inc,
                    exclusion_criteria=exc,
                    enrollment_target=t.enrollment_target,
                    site_count=t.site_count,
                    start_date=t.start_date,
                    end_date=t.end_date,
                )
                record = _TrialRecord(
                    id=str(t.id),
                    create=trial_create,
                )
                record.created_at = t.created_at

                merged[str(t.id)] = record

            self._trials = merged

            # Load enrollments for each trial
            enrollment_result = await session.execute(select(TrialEnrollment))
            db_enrollments = enrollment_result.scalars().all()

            for e in db_enrollments:
                trial_record = self._trials.get(str(e.trial_id))
                if not trial_record:
                    continue

                enrollment_create = EnrollmentCreate(
                    patient_id=e.patient_id,
                    enrollment_status=e.enrollment_status,
                    site_id=e.site_id,
                    notes=e.notes,
                )
                enrollment = _EnrollmentRecord(
                    id=str(e.id),
                    trial_id=str(e.trial_id),
                    create=enrollment_create,
                )
                enrollment.match_score = e.match_score
                enrollment.criteria_met = e.criteria_met
                enrollment.criteria_failed = e.criteria_failed
                enrollment.screening_date = e.screening_date
                enrollment.enrollment_date = e.enrollment_date
                enrollment.withdrawal_date = e.withdrawal_date
                enrollment.withdrawal_reason = e.withdrawal_reason
                enrollment.created_at = e.created_at

                trial_record.enrollments[e.patient_id] = enrollment

            self._loaded_from_db = True
            logger.info(
                f"Loaded {len(db_trials)} trials and {len(db_enrollments)} "
                f"enrollments from DB"
            )

        except Exception:
            logger.warning("Could not load trials from DB; keeping in-memory data", exc_info=True)
            self._loaded_from_db = True

    async def _ensure_loaded(self, session: AsyncSession) -> None:
        """Ensure trials are loaded from DB on first request."""
        if not self._loaded_from_db:
            await self.load_from_db(session)

    # ==========================================================================
    # Criterion SQL helpers
    # ==========================================================================

    def _criterion_patient_query(
        self,
        criterion: dict,
    ) -> select | None:
        """Build a SELECT DISTINCT patient_id query for a single criterion.

        Returns None for demographic criteria (handled separately via KGNode)
        or unknown criterion types.
        """
        ctype = criterion.get("criterion_type")
        codes = criterion.get("codes", [])
        display_terms = [c["display"] for c in codes if c.get("display")]

        if not display_terms and ctype != "demographic":
            return None

        domain_map = {
            "condition": Domain.CONDITION,
            "drug": Domain.DRUG,
            "measurement": Domain.MEASUREMENT,
            "procedure": Domain.PROCEDURE,
            "observation": Domain.OBSERVATION,
        }

        if ctype == "demographic":
            # Demographic filtering is done separately against KGNode
            return None

        domain = domain_map.get(ctype)
        if domain is None:
            logger.warning(f"Unknown criterion type: {ctype}")
            return None

        like_clauses = [ClinicalFact.concept_name.ilike(f"%{term}%") for term in display_terms]

        filters = [
            ClinicalFact.domain == domain,
            ClinicalFact.assertion == Assertion.PRESENT,
            or_(*like_clauses),
        ]

        # Measurement value range filtering
        if ctype == "measurement" and criterion.get("value_range"):
            vr = criterion["value_range"]
            if vr.get("min_value") is not None:
                filters.append(cast(ClinicalFact.value, SAFloat) >= vr["min_value"])
            if vr.get("max_value") is not None:
                filters.append(cast(ClinicalFact.value, SAFloat) <= vr["max_value"])

        return select(ClinicalFact.patient_id).where(and_(*filters)).distinct()

    async def _get_demographic_patient_ids(
        self,
        criterion: dict,
        session: AsyncSession,
    ) -> set[str]:
        """Query KGNode for patients matching demographic criteria (age range)."""
        age_range = criterion.get("age_range")
        if not age_range:
            # No constraint means everyone matches
            stmt = select(KGNode.patient_id).where(
                KGNode.node_type == NodeType.PATIENT,
                KGNode.deleted_at.is_(None),
            ).distinct()
            result = await session.execute(stmt)
            return set(result.scalars().all())

        # Get all patient nodes and filter by birth_date in properties JSON
        stmt = select(KGNode.patient_id, KGNode.properties).where(
            KGNode.node_type == NodeType.PATIENT,
            KGNode.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        rows = result.all()

        now = datetime.now(timezone.utc)
        matching = set()
        min_age = age_range.get("min_age")
        max_age = age_range.get("max_age")

        for patient_id, props in rows:
            birth_date_str = (props or {}).get("birth_date")
            if not birth_date_str:
                continue
            try:
                birth_date = datetime.fromisoformat(birth_date_str)
                if birth_date.tzinfo is None:
                    birth_date = birth_date.replace(tzinfo=timezone.utc)
                age = (now - birth_date).days / 365.25
                if min_age is not None and age < min_age:
                    continue
                if max_age is not None and age > max_age:
                    continue
                matching.add(patient_id)
            except (ValueError, TypeError):
                continue

        return matching

    # ==========================================================================
    # Trial CRUD
    # ==========================================================================

    def create_trial(self, create: TrialCreate) -> TrialResponse:
        """Create a new clinical trial."""
        trial_id = str(uuid4())

        record = _TrialRecord(
            id=trial_id,
            create=create,
        )
        self._trials[trial_id] = record

        logger.info(f"Created trial: {trial_id} - {create.name}")
        return record.to_response()

    async def get_trial(self, trial_id: str, *, session: AsyncSession | None = None) -> TrialResponse | None:
        """Get a trial by ID."""
        if session:
            await self._ensure_loaded(session)
        record = self._trials.get(trial_id)
        return record.to_response() if record else None

    async def list_trials(
        self,
        status: TrialStatus | None = None,
        sponsor: str | None = None,
        therapeutic_area: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> tuple[list[TrialSummary], int]:
        """List trials with filtering."""
        if session:
            await self._ensure_loaded(session)
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

        if update.inclusion_criteria is not None:
            record.inclusion_criteria = update.inclusion_criteria
        if update.exclusion_criteria is not None:
            record.exclusion_criteria = update.exclusion_criteria

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

    async def screen_patients(
        self,
        trial_id: str,
        request: ScreeningRequest | None = None,
        *,
        session: AsyncSession,
    ) -> ScreeningResponse | None:
        """Screen patients against trial eligibility criteria.

        Queries the clinical_facts table for each inclusion/exclusion criterion,
        intersects inclusion results (AND logic), subtracts exclusion matches,
        and returns scored candidates.
        """
        await self._ensure_loaded(session)
        record = self._trials.get(trial_id)
        if not record:
            return None

        start_time = time.perf_counter()

        inclusion_criteria = record.inclusion_criteria or {}
        inclusion_list = inclusion_criteria.get("criteria", [])
        exclusion_criteria = record.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        # --- Gather all patients in the DB as the screening universe ---
        all_patients_stmt = select(ClinicalFact.patient_id).distinct()
        all_result = await session.execute(all_patients_stmt)
        all_patient_ids: set[str] = set(all_result.scalars().all())

        # If request specifies patient_ids, restrict universe
        if request and request.patient_ids:
            all_patient_ids = all_patient_ids & set(request.patient_ids)

        total_screened = len(all_patient_ids)

        # --- Inclusion: intersect matching patient sets (AND logic) ---
        inclusion_sets: list[set[str]] = []
        for criterion in inclusion_list:
            ctype = criterion.get("criterion_type")
            if ctype == "demographic":
                matching = await self._get_demographic_patient_ids(criterion, session)
                inclusion_sets.append(matching & all_patient_ids)
            else:
                stmt = self._criterion_patient_query(criterion)
                if stmt is not None:
                    result = await session.execute(stmt)
                    matching = set(result.scalars().all())
                    inclusion_sets.append(matching & all_patient_ids)

        if inclusion_sets:
            included_patients = inclusion_sets[0]
            for s in inclusion_sets[1:]:
                included_patients = included_patients & s
        else:
            included_patients = all_patient_ids

        # --- Exclusion: union matching patient sets, then subtract ---
        excluded_patients: set[str] = set()
        exclusion_breakdown: dict[str, int] = {}
        for criterion in exclusion_list:
            name = criterion.get("name", criterion.get("criterion_type", "Unknown"))
            ctype = criterion.get("criterion_type")

            if ctype == "demographic":
                matching = await self._get_demographic_patient_ids(criterion, session)
            else:
                stmt = self._criterion_patient_query(criterion)
                if stmt is not None:
                    result = await session.execute(stmt)
                    matching = set(result.scalars().all())
                else:
                    matching = set()

            overlap = matching & included_patients
            exclusion_breakdown[name] = len(overlap)
            excluded_patients |= overlap

        eligible_patients = included_patients - excluded_patients
        eligible_count = len(eligible_patients)

        # --- Compute data_insufficient_count ---
        # Patients who matched NONE of the inclusion criteria sets likely
        # lack data. This is an approximation for the batch-level count.
        if inclusion_sets:
            patients_in_any_set = set()
            for s in inclusion_sets:
                patients_in_any_set |= s
            # Patients not appearing in any criterion match set
            data_insufficient_count = len(all_patient_ids - patients_in_any_set)
        else:
            data_insufficient_count = 0

        # --- Build candidate list with per-criterion detail ---
        limit = request.limit if request else 100
        min_score = request.min_match_score if request else 0.0
        candidates = await self._build_real_candidates(
            record, eligible_patients, included_patients, session, limit, min_score,
        )

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
            data_insufficient_count=data_insufficient_count,
            enrollment_target=record.enrollment_target,
            enrollment_rate=round(enrollment_rate, 2),
            candidates=candidates,
            demographics_summary=None,
            exclusion_breakdown=exclusion_breakdown,
            requires_clinician_review=True,
            cds_disclaimer=CDS_DISCLAIMER,
        )

    # Weight map for criterion types used in weighted score calculation.
    _CRITERION_WEIGHT: dict[str, float] = {
        "condition": 1.0,
        "measurement": 0.8,
        "demographic": 0.5,
    }

    # Map criterion types to human-readable domain labels for completeness reports.
    _DOMAIN_LABEL: dict[str, str] = {
        "condition": "conditions",
        "drug": "medications",
        "measurement": "lab_results",
        "procedure": "procedures",
        "observation": "observations",
        "demographic": "demographics",
    }

    async def _evaluate_criterion(
        self,
        criterion: dict,
        patient_id: str,
        session: AsyncSession,
        *,
        is_exclusion: bool = False,
    ) -> CriterionResult:
        """Evaluate a single criterion for a patient with evidence tracking.

        Returns a CriterionResult with fact-level audit data, confidence
        scores, and a weighted importance value.

        Distinguishes between:
        - UNKNOWN: No data exists in the relevant domain for this patient.
        - NOT_MET: Data exists in the domain but does not satisfy the criterion.
        """
        name = criterion.get("name", criterion.get("criterion_type", "Unknown"))
        ctype = criterion.get("criterion_type", "unknown")
        weight = self._CRITERION_WEIGHT.get(ctype, 1.0)
        domain_label = self._DOMAIN_LABEL.get(ctype)

        # --- Demographic criteria (no ClinicalFact, uses KGNode) ---
        if ctype == "demographic":
            matching = await self._get_demographic_patient_ids(criterion, session)
            matched = patient_id in matching

            # Fetch patient properties for evidence summary (VP-Product-2)
            demo_props_stmt = select(KGNode.properties).where(
                KGNode.patient_id == patient_id,
                KGNode.node_type == NodeType.PATIENT,
                KGNode.deleted_at.is_(None),
            ).limit(1)
            demo_props_result = await session.execute(demo_props_stmt)
            demo_props = demo_props_result.scalar_one_or_none()

            # Build demographic evidence summary
            demo_summary: str | None = None
            demo_conf_explanation: str | None = None
            if demo_props:
                birth_date_str = (demo_props or {}).get("birth_date")
                gender = (demo_props or {}).get("gender", "Unknown")
                if birth_date_str:
                    try:
                        bd = datetime.fromisoformat(birth_date_str)
                        if bd.tzinfo is None:
                            bd = bd.replace(tzinfo=timezone.utc)
                        age = int((datetime.now(timezone.utc) - bd).days / 365.25)
                        age_range = criterion.get("age_range", {})
                        min_age = age_range.get("min_age")
                        max_age = age_range.get("max_age")
                        range_str = ""
                        if min_age is not None and max_age is not None:
                            range_str = f" (required: {min_age}-{max_age})"
                        elif min_age is not None:
                            range_str = f" (required: >= {min_age})"
                        elif max_age is not None:
                            range_str = f" (required: <= {max_age})"
                        if matched:
                            demo_summary = (
                                f"Patient is {age} years old (DOB: {bd.strftime('%Y-%m-%d')}), "
                                f"gender: {gender}. Meets demographic requirements{range_str}."
                            )
                        else:
                            demo_summary = (
                                f"Patient is {age} years old (DOB: {bd.strftime('%Y-%m-%d')}), "
                                f"gender: {gender}. Does not meet demographic requirements{range_str}."
                            )
                        demo_conf_explanation = "High confidence: demographic data from patient record"
                    except (ValueError, TypeError):
                        demo_summary = f"Patient gender: {gender}. Birth date could not be parsed."
                        demo_conf_explanation = "Unable to compute age from birth date"

            if matched:
                return CriterionResult(
                    criterion_name=name,
                    criterion_type=ctype,
                    status="PASS",
                    evidence_fact_ids=[],
                    confidence=1.0,
                    details="Demographic matched",
                    weight=weight,
                    evidence_summary=demo_summary or "Patient meets demographic requirements",
                    confidence_explanation=demo_conf_explanation or "High confidence: demographic data from patient record",
                )

            if demo_props:
                birth_date_str = (demo_props or {}).get("birth_date")
                has_birth_date = bool(birth_date_str)

                if has_birth_date:
                    # Has demographic data but doesn't meet criterion
                    return CriterionResult(
                        criterion_name=name,
                        criterion_type=ctype,
                        status="NOT_MET",
                        evidence_fact_ids=[],
                        confidence=1.0,
                        details="Demographic data exists but criterion not satisfied",
                        weight=weight,
                        evidence_summary=demo_summary or f"Patient does not meet demographic requirements for '{name}'",
                        confidence_explanation=demo_conf_explanation or "High confidence: demographic data from patient record does not satisfy criterion",
                    )

            # No demographic data available
            return CriterionResult(
                criterion_name=name,
                criterion_type=ctype,
                status="UNKNOWN",
                evidence_fact_ids=[],
                confidence=0.0,
                details="No demographic data available for this patient",
                weight=weight,
                missing_domain=domain_label,
                evidence_summary="Insufficient demographic data to evaluate this criterion",
                confidence_explanation="Unable to evaluate: missing birth date or demographic information",
            )

        # --- Non-demographic: query ClinicalFact with id + confidence ---
        codes = criterion.get("codes", [])
        display_terms = [c["display"] for c in codes if c.get("display")]
        if not display_terms:
            return CriterionResult(
                criterion_name=name,
                criterion_type=ctype,
                status="UNKNOWN",
                evidence_fact_ids=[],
                confidence=0.0,
                details="No display terms available for criterion",
                weight=weight,
                missing_domain=domain_label,
            )

        domain_map = {
            "condition": Domain.CONDITION,
            "drug": Domain.DRUG,
            "measurement": Domain.MEASUREMENT,
            "procedure": Domain.PROCEDURE,
            "observation": Domain.OBSERVATION,
        }
        domain = domain_map.get(ctype)
        if domain is None:
            return CriterionResult(
                criterion_name=name,
                criterion_type=ctype,
                status="UNKNOWN",
                evidence_fact_ids=[],
                confidence=0.0,
                details=f"Unsupported criterion type: {ctype}",
                weight=weight,
                missing_domain=domain_label,
            )

        like_clauses = [ClinicalFact.concept_name.ilike(f"%{term}%") for term in display_terms]
        filters = [
            ClinicalFact.patient_id == patient_id,
            ClinicalFact.domain == domain,
            ClinicalFact.assertion == Assertion.PRESENT,
            or_(*like_clauses),
        ]

        # Measurement value range filtering
        if ctype == "measurement" and criterion.get("value_range"):
            vr = criterion["value_range"]
            if vr.get("min_value") is not None:
                filters.append(cast(ClinicalFact.value, SAFloat) >= vr["min_value"])
            if vr.get("max_value") is not None:
                filters.append(cast(ClinicalFact.value, SAFloat) <= vr["max_value"])

        # Fetch fact details for evidence summaries (VP-Product-2)
        stmt = select(
            ClinicalFact.id,
            ClinicalFact.confidence,
            ClinicalFact.concept_name,
            ClinicalFact.value,
            ClinicalFact.unit,
            ClinicalFact.start_date,
            ClinicalFact.omop_concept_id,
        ).where(and_(*filters))
        result = await session.execute(stmt)
        facts = result.all()

        if not facts:
            # Distinguish NOT_MET vs UNKNOWN: check if patient has ANY data
            # in this domain (regardless of concept match).
            domain_check_stmt = select(ClinicalFact.id).where(
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.domain == domain,
                ClinicalFact.assertion == Assertion.PRESENT,
            ).limit(1)
            domain_check_result = await session.execute(domain_check_stmt)
            has_domain_data = domain_check_result.scalar_one_or_none() is not None

            if has_domain_data:
                return CriterionResult(
                    criterion_name=name,
                    criterion_type=ctype,
                    status="NOT_MET",
                    evidence_fact_ids=[],
                    confidence=0.0,
                    details=f"Patient has {domain.value} data but no match for this criterion",
                    weight=weight,
                    evidence_summary=(
                        f"Patient has {domain.value} data, but no match found for "
                        f"'{name}'"
                    ),
                    confidence_explanation=(
                        "Criterion not satisfied: data exists in the domain but "
                        "does not match required codes or values"
                    ),
                )
            else:
                return CriterionResult(
                    criterion_name=name,
                    criterion_type=ctype,
                    status="UNKNOWN",
                    evidence_fact_ids=[],
                    confidence=0.0,
                    details=f"No {domain.value} data available for this patient",
                    weight=weight,
                    missing_domain=domain_label,
                    evidence_summary=(
                        f"No {domain.value} data available for this patient "
                        f"to evaluate '{name}'"
                    ),
                    confidence_explanation=(
                        "Unable to evaluate: no data in the relevant clinical domain"
                    ),
                )

        max_confidence = max(f.confidence for f in facts)
        fact_ids = [str(f.id) for f in facts]

        # Determine whether this is a safety-critical hard block.
        # An exclusion criterion matched with high confidence (>0.7) and
        # assertion=PRESENT means the patient has a contraindication.
        # This is a HARD STOP -- no automated override is permitted.
        is_safety_block = is_exclusion and max_confidence > 0.7

        if max_confidence > 0.7:
            status = "PASS" if not is_exclusion else "FAIL"
            details = f"Matched {len(facts)} fact(s), max confidence {max_confidence:.2f}"
            if is_safety_block:
                details = (
                    f"SAFETY BLOCK: Exclusion criterion matched with high confidence "
                    f"({max_confidence:.2f}). Patient has a contraindication for this "
                    f"trial. This is a hard stop -- no automated override permitted. "
                    f"Matched {len(facts)} fact(s)."
                )
        elif max_confidence > 0.3:
            status = "POSSIBLE_MATCH"
            details = f"Low-confidence match ({max_confidence:.2f}), {len(facts)} fact(s)"
        else:
            status = "UNKNOWN"
            details = f"Very low confidence ({max_confidence:.2f}), treating as unknown"

        # --- Build evidence summary (VP-Product-2) ---
        evidence_parts: list[str] = []
        for f in facts[:3]:  # Limit to top 3 for readability
            concept = f.concept_name
            omop_id = f.omop_concept_id
            code_info = f" (OMOP:{omop_id})" if omop_id else ""
            date_str = f.start_date.strftime("%Y-%m-%d") if f.start_date else "date unknown"
            if ctype == "measurement" and f.value:
                unit_str = f" {f.unit}" if f.unit else ""
                evidence_parts.append(f"{concept}: {f.value}{unit_str} (recorded {date_str})")
            else:
                evidence_parts.append(f"{concept}{code_info}, recorded {date_str}")

        evidence_text = "; ".join(evidence_parts)
        if len(facts) > 3:
            evidence_text += f" (+{len(facts) - 3} more)"

        status_verb_map = {
            "PASS": "is satisfied",
            "FAIL": "is triggered (exclusion matched)",
            "POSSIBLE_MATCH": "has a possible match (needs review)",
            "UNKNOWN": "cannot be evaluated",
        }
        status_verb = status_verb_map.get(status, status.lower())
        evidence_summary = f"Patient has {evidence_text}. Criterion '{name}' {status_verb}."

        # --- Build confidence explanation ---
        conf_level = "High" if max_confidence >= 0.8 else "Medium" if max_confidence >= 0.6 else "Low"
        type_labels = {
            "condition": "diagnosis code",
            "measurement": "lab result",
            "drug": "medication record",
            "procedure": "procedure record",
            "observation": "clinical observation",
        }
        type_label = type_labels.get(ctype, "clinical record")
        best_fact = facts[0]
        conf_concept = best_fact.concept_name
        if best_fact.omop_concept_id:
            conf_concept += f" (OMOP:{best_fact.omop_concept_id})"
        confidence_explanation = (
            f"{conf_level} confidence ({max_confidence:.0%}): "
            f"{type_label} match on {conf_concept}"
        )

        return CriterionResult(
            criterion_name=name,
            criterion_type=ctype,
            status=status,
            evidence_fact_ids=fact_ids,
            confidence=round(max_confidence, 4),
            details=details,
            weight=weight,
            safety_block=is_safety_block,
            evidence_summary=evidence_summary,
            confidence_explanation=confidence_explanation,
        )

    def _compute_data_completeness(
        self,
        criteria_details: list[CriterionResult],
    ) -> DataCompletenessScore:
        """Compute data completeness score from criterion evaluation results.

        Classifies each criterion as evaluable (we have data) or not (UNKNOWN),
        and collects the missing data domains.
        """
        total = len(criteria_details)
        unknown_count = 0
        not_met_count = 0
        missing_domains: list[str] = []

        for cr in criteria_details:
            if cr.status == "UNKNOWN":
                unknown_count += 1
                if cr.missing_domain and cr.missing_domain not in missing_domains:
                    missing_domains.append(cr.missing_domain)
            elif cr.status == "NOT_MET":
                not_met_count += 1

        evaluable = total - unknown_count
        completeness = evaluable / total if total > 0 else 1.0

        # Generate recommendation based on what's missing
        recommendation: str | None = None
        if missing_domains:
            domain_labels = {
                "lab_results": "laboratory results",
                "conditions": "condition/diagnosis records",
                "medications": "medication records",
                "procedures": "procedure records",
                "demographics": "demographic information (age, sex)",
                "observations": "clinical observations",
            }
            readable = [domain_labels.get(d, d) for d in missing_domains]
            if len(readable) == 1:
                recommendation = f"Obtain {readable[0]} to complete eligibility evaluation"
            else:
                recommendation = f"Obtain {', '.join(readable[:-1])} and {readable[-1]} to complete eligibility evaluation"

        return DataCompletenessScore(
            overall_completeness=round(completeness, 3),
            evaluable_criteria=evaluable,
            total_criteria=total,
            unknown_criteria=unknown_count,
            not_met_criteria=not_met_count,
            missing_domains=missing_domains,
            recommendation=recommendation,
        )

    async def check_patient_eligibility(
        self,
        trial_id: str,
        patient_id: str,
        *,
        session: AsyncSession,
    ) -> PatientEligibility | None:
        """Check a single patient's eligibility for a trial.

        Queries the clinical_facts table for each criterion, collects
        evidence fact IDs and confidence scores, and returns a weighted
        match score with a full per-criterion audit trail.

        Distinguishes between:
        - NOT_MET: data exists in the domain but doesn't satisfy the criterion
        - UNKNOWN: no data available to evaluate the criterion
        """
        await self._ensure_loaded(session)
        record = self._trials.get(trial_id)
        if not record:
            return None

        screening_ts = datetime.now(timezone.utc)

        inclusion_criteria = record.inclusion_criteria or {}
        inclusion_list = inclusion_criteria.get("criteria", [])
        exclusion_criteria = record.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        inclusion_met: list[str] = []
        missing_data: list[str] = []
        criteria_details: list[CriterionResult] = []

        # --- Evaluate inclusion criteria ---
        for criterion in inclusion_list:
            cr = await self._evaluate_criterion(criterion, patient_id, session)
            criteria_details.append(cr)

            if cr.status == "PASS":
                inclusion_met.append(cr.criterion_name)
            elif cr.status == "POSSIBLE_MATCH":
                # Possible matches are noted but do not count as met
                missing_data.append(cr.criterion_name)
            else:
                # Both UNKNOWN and NOT_MET go to missing_data
                missing_data.append(cr.criterion_name)

        # --- Evaluate exclusion criteria ---
        exclusion_triggered: list[str] = []
        safety_blocked_reasons: list[str] = []
        for criterion in exclusion_list:
            cr = await self._evaluate_criterion(
                criterion, patient_id, session, is_exclusion=True,
            )
            criteria_details.append(cr)

            if cr.status == "FAIL":
                # Exclusion criterion matched with high confidence
                exclusion_triggered.append(cr.criterion_name)

            # CMO-5: Patient Safety Guardrails -- hard stop enforcement.
            # When safety_block is True, this is a contraindication that
            # MUST prevent the patient from being considered eligible.
            # There is no automated override path.
            if cr.safety_block:
                reason = (
                    f"Exclusion criterion '{cr.criterion_name}' matched with "
                    f"confidence {cr.confidence:.2f} -- patient has a "
                    f"contraindication (evidence: {len(cr.evidence_fact_ids)} "
                    f"fact(s)). HARD STOP: no automated override permitted."
                )
                safety_blocked_reasons.append(reason)

        is_safety_blocked = len(safety_blocked_reasons) > 0

        # --- Log safety block events prominently ---
        if is_safety_blocked:
            self._log_safety_block(
                patient_id=patient_id,
                trial_id=trial_id,
                trial_name=record.name,
                safety_blocked_reasons=safety_blocked_reasons,
                exclusion_details=[
                    cr for cr in criteria_details if cr.safety_block
                ],
            )

        # --- Weighted match score ---
        # Count evaluable criteria (not UNKNOWN) in the denominator.
        # NOT_MET is evaluable (we have data, it just doesn't match).
        evaluable_weight = 0.0
        met_weight = 0.0
        evaluable_count = 0
        for cr in criteria_details:
            if cr.status in ("PASS", "FAIL", "POSSIBLE_MATCH", "NOT_MET"):
                evaluable_weight += cr.weight
                evaluable_count += 1
                if cr.status == "PASS":
                    met_weight += cr.weight

        if evaluable_weight > 0:
            score = met_weight / evaluable_weight
        else:
            score = 0.0

        # Any exclusion triggered drops score to zero
        if exclusion_triggered:
            score = 0.0

        # CMO-5: Safety block forces score to 0.0 unconditionally.
        # This is a belt-and-suspenders check on top of the exclusion_triggered
        # logic above.  Even if a future code path somehow bypasses exclusion
        # tracking, the safety block still forces the score to zero.
        if is_safety_blocked:
            score = 0.0

        eligible = (
            len(inclusion_met) == len(inclusion_list) and len(exclusion_triggered) == 0
        )

        # CMO-5: Safety block forces ineligible unconditionally.
        # This is the HARD STOP: no matter what the inclusion criteria say,
        # a safety-blocked patient is NEVER eligible.
        if is_safety_blocked:
            eligible = False

        # --- Compute data completeness score ---
        data_completeness = self._compute_data_completeness(criteria_details)

        return PatientEligibility(
            patient_id=patient_id,
            eligible=eligible,
            match_score=round(score, 3),
            inclusion_met=inclusion_met,
            inclusion_total=len(inclusion_list),
            exclusion_triggered=exclusion_triggered,
            exclusion_total=len(exclusion_list),
            missing_data=missing_data,
            criteria_details=criteria_details,
            evaluable_criteria=evaluable_count,
            screening_timestamp=screening_ts,
            requires_clinician_review=True,
            review_disclaimer=CDS_DISCLAIMER,
            data_completeness=data_completeness,
            safety_blocked=is_safety_blocked,
            safety_blocked_reasons=safety_blocked_reasons,
        )

    def _log_safety_block(
        self,
        *,
        patient_id: str,
        trial_id: str,
        trial_name: str,
        safety_blocked_reasons: list[str],
        exclusion_details: list[CriterionResult],
    ) -> None:
        """Log a SafetyBlockEvent when a patient is blocked from a trial.

        CMO-5: Patient Safety Guardrails.

        This method emits structured log records to both the dedicated
        patient_safety logger (WARNING level) and the audit trail.  Safety
        block events are the most critical patient-safety signal in the
        screening pipeline and MUST be visible in monitoring dashboards.
        """
        block_summary = (
            f"SAFETY BLOCK: Patient {patient_id} blocked from trial "
            f"'{trial_name}' ({trial_id}). "
            f"{len(safety_blocked_reasons)} exclusion criterion/criteria triggered hard stop."
        )

        # Structured detail for each blocking criterion
        criterion_audit: list[dict[str, Any]] = []
        for cr in exclusion_details:
            criterion_audit.append({
                "criterion_name": cr.criterion_name,
                "criterion_type": cr.criterion_type,
                "confidence": cr.confidence,
                "evidence_fact_ids": cr.evidence_fact_ids,
                "details": cr.details,
            })

        # --- Emit to dedicated patient_safety logger at WARNING level ---
        safety_logger.warning(
            block_summary,
            extra={
                "event_type": "SafetyBlockEvent",
                "patient_id": patient_id,
                "trial_id": trial_id,
                "trial_name": trial_name,
                "safety_blocked_reasons": safety_blocked_reasons,
                "blocking_criteria": criterion_audit,
            },
        )

        # --- Emit to the standard service logger ---
        logger.warning(block_summary)

        # --- Emit to the audit trail ---
        log_audit(
            action=AuditAction.READ,
            resource_type="safety_block",
            resource_id=trial_id,
            patient_id=patient_id,
            details={
                "event_type": "SafetyBlockEvent",
                "trial_name": trial_name,
                "safety_blocked_reasons": safety_blocked_reasons,
                "blocking_criteria": criterion_audit,
            },
            success=True,
        )

    async def _build_real_candidates(
        self,
        trial: _TrialRecord,
        eligible_patients: set[str],
        included_patients: set[str],
        session: AsyncSession,
        limit: int,
        min_score: float,
    ) -> list[PatientEligibility]:
        """Build candidate list from real query results.

        For eligible patients, all inclusion criteria are met and no exclusion
        criteria are triggered. For patients in included_patients but not
        eligible, they met inclusion but triggered an exclusion.
        """
        inclusion_criteria = trial.inclusion_criteria or {}
        inclusion_list = inclusion_criteria.get("criteria", [])
        exclusion_criteria = trial.exclusion_criteria or {}
        exclusion_list = exclusion_criteria.get("criteria", [])

        all_inclusion_names = [
            c.get("name", c.get("criterion_type", "Unknown"))
            for c in inclusion_list
        ]

        total_criteria = len(inclusion_list) + len(exclusion_list)

        candidates: list[PatientEligibility] = []
        for patient_id in sorted(eligible_patients):
            if len(candidates) >= limit:
                break

            score = 1.0  # All inclusion met, no exclusion triggered
            if score >= min_score:
                # Eligible patients passed all criteria -> full completeness
                completeness = DataCompletenessScore(
                    overall_completeness=1.0,
                    evaluable_criteria=total_criteria,
                    total_criteria=total_criteria,
                    unknown_criteria=0,
                    not_met_criteria=0,
                    missing_domains=[],
                    recommendation=None,
                )
                candidates.append(PatientEligibility(
                    patient_id=patient_id,
                    eligible=True,
                    match_score=round(score, 3),
                    inclusion_met=list(all_inclusion_names),
                    inclusion_total=len(inclusion_list),
                    exclusion_triggered=[],
                    exclusion_total=len(exclusion_list),
                    missing_data=[],
                    requires_clinician_review=True,
                    review_disclaimer=CDS_DISCLAIMER,
                    data_completeness=completeness,
                ))

        candidates.sort(key=lambda c: c.match_score, reverse=True)
        return candidates

    # ==========================================================================
    # Auto-Screening
    # ==========================================================================

    async def auto_screen_patient(
        self,
        patient_id: str,
        *,
        session: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Auto-screen a patient against all active trials after FHIR import.

        CMO-5: If check_patient_eligibility sets safety_blocked=True, the
        patient is NEVER enrolled as a CANDIDATE, regardless of inclusion
        score.  The safety block is logged and included in the result dict.
        """
        await self._ensure_loaded(session)
        results = []
        for trial_id, record in self._trials.items():
            if record.status != TrialStatus.RECRUITING:
                continue
            eligibility = await self.check_patient_eligibility(
                trial_id, patient_id, session=session
            )
            if not eligibility:
                continue
            result: dict[str, Any] = {
                "trial_id": trial_id,
                "trial_name": record.name,
                "eligible": eligibility.eligible,
                "match_score": eligibility.match_score,
                "safety_blocked": eligibility.safety_blocked,
            }

            # CMO-5: Safety block prevents auto-enrollment.
            # This is a HARD STOP -- no automated override path.
            if eligibility.safety_blocked:
                result["safety_blocked_reasons"] = eligibility.safety_blocked_reasons
                logger.warning(
                    f"Auto-screen: patient {patient_id} SAFETY BLOCKED from "
                    f"trial '{record.name}' ({trial_id}). "
                    f"Enrollment prevented by hard stop."
                )
            elif eligibility.eligible and eligibility.match_score > 0.5:
                # Only create CANDIDATE enrollment when NOT safety-blocked
                existing = record.enrollments.get(patient_id)
                if not existing:
                    enrollment = await self.enroll_patient(
                        trial_id,
                        EnrollmentCreate(patient_id=patient_id),
                        session=session,
                    )
                    if enrollment:
                        result["enrollment_id"] = str(enrollment.id)
                        result["enrollment_status"] = "candidate"

            results.append(result)
            logger.info(
                f"Auto-screen: patient {patient_id} vs {record.name}: "
                f"eligible={eligibility.eligible}, score={eligibility.match_score}, "
                f"safety_blocked={eligibility.safety_blocked}"
            )
        return results

    # ==========================================================================
    # Enrollment Management
    # ==========================================================================

    async def enroll_patient(
        self,
        trial_id: str,
        create: EnrollmentCreate,
        *,
        session: AsyncSession,
    ) -> EnrollmentResponse | None:
        """Add a patient to a trial's enrollment pipeline."""
        await self._ensure_loaded(session)
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
        eligibility = await self.check_patient_eligibility(
            trial_id, create.patient_id, session=session
        )
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

    async def get_dashboard(self, trial_id: str, *, session: AsyncSession | None = None) -> TrialDashboard | None:
        """Get enrollment dashboard for a trial."""
        if session:
            await self._ensure_loaded(session)
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

    async def get_stats(self, *, session: AsyncSession | None = None) -> dict[str, Any]:
        """Get service-level statistics."""
        if session:
            await self._ensure_loaded(session)
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
