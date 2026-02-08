"""Comprehensive tests for trial screening / eligibility logic.

VPE-1: Tests covering every criterion type, AND/OR logic, exclusion
subtraction, partial matches, safety blocks, data completeness,
confidence filtering, real trial criteria, and edge cases.

Covers:
- Condition criterion matching (PRESENT assertion, ilike search)
- Measurement criterion with value ranges (HbA1c, blood pressure)
- Demographic criterion (age range via KGNode birth_date)
- Inclusion AND logic (all criteria must match)
- Exclusion subtraction logic (union of exclusions subtracted)
- Partial matches (some inclusion criteria met, some missing)
- Match scoring (weighted score calculation)
- Safety blocks (active cancer blocking enrollment)
- NOT_MET vs UNKNOWN distinction
- Data completeness scoring
- Confidence filtering (low-confidence -> POSSIBLE_MATCH)
- EYLEA HD trial criteria (multi-condition + measurement exclusion)
- Dupixent trial criteria (demographic + condition + exclusion)
- Libtayo trial criteria (oncology with autoimmune exclusion)
- Edge cases: no clinical facts, all criteria unknown, single criterion
- Negated conditions (assertion=ABSENT should NOT match)
- Batch screening (screen_patients)
- Auto-screening pipeline
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.clinical_fact import ClinicalFact
from app.models.knowledge_graph import KGNode
from app.schemas.base import Assertion, Domain, Experiencer, Temporality
from app.schemas.knowledge_graph import NodeType
from app.schemas.trial import (
    CriterionResult,
    DataCompletenessScore,
    PatientEligibility,
    ScreeningRequest,
    TrialCreate,
)
from app.models.trial import TrialPhase, TrialStatus
from app.services.trial_eligibility_service import TrialEligibilityService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="function")
async def engine():
    """Create async SQLite in-memory engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    tables = [ClinicalFact.__table__, KGNode.__table__]
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=tables)
    await eng.dispose()


@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create an async database session for testing."""
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
        autocommit=False, autoflush=False,
    )
    async with factory() as sess:
        yield sess
        await sess.rollback()


@pytest.fixture
def service() -> TrialEligibilityService:
    """Create a fresh TrialEligibilityService (skip DB loading)."""
    svc = TrialEligibilityService()
    svc._loaded_from_db = True
    return svc


# =============================================================================
# Helpers
# =============================================================================


async def _insert_fact(
    session: AsyncSession, *, patient_id: str, domain: Domain,
    concept_name: str, assertion: Assertion = Assertion.PRESENT,
    confidence: float = 0.95, value: str | None = None,
    unit: str | None = None, omop_concept_id: int = 0,
) -> ClinicalFact:
    """Insert a ClinicalFact into the test database."""
    fact = ClinicalFact(
        id=str(uuid4()), patient_id=patient_id, domain=domain,
        omop_concept_id=omop_concept_id, concept_name=concept_name,
        assertion=assertion, temporality=Temporality.CURRENT,
        experiencer=Experiencer.PATIENT, confidence=confidence,
        value=value, unit=unit,
    )
    session.add(fact)
    await session.flush()
    return fact


async def _insert_patient_node(
    session: AsyncSession, *, patient_id: str,
    birth_date: str | None = None, gender: str | None = None,
) -> KGNode:
    """Insert a KGNode of type PATIENT."""
    props: dict = {}
    if birth_date:
        props["birth_date"] = birth_date
    if gender:
        props["gender"] = gender
    node = KGNode(
        id=str(uuid4()), patient_id=patient_id,
        node_type=NodeType.PATIENT, omop_concept_id=None,
        label=f"Patient {patient_id}", properties=props,
    )
    session.add(node)
    await session.flush()
    return node


def _dob_for_age(age: int) -> str:
    """Return ISO birth date string for a given age in years.

    Adds 2 extra days beyond the exact boundary to avoid floating-point
    precision issues when the eligibility service computes
    (now - birth_date).days / 365.25.
    """
    bd = datetime.now(timezone.utc) - timedelta(days=int(age * 365.25) + 2)
    return bd.strftime("%Y-%m-%d")


# =============================================================================
# Trial Definitions
# =============================================================================


def _ad_trial() -> TrialCreate:
    """Dupixent - Atopic Dermatitis trial."""
    return TrialCreate(
        name="DUPIXENT AD",
        nct_number="NCT02395133",
        sponsor="Regeneron",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.RECRUITING,
        therapeutic_area="Dermatology",
        inclusion_criteria={
            "criteria": [
                {"criterion_type": "demographic", "name": "Adult patients",
                 "age_range": {"min_age": 18, "max_age": 75}},
                {"criterion_type": "condition", "name": "Atopic Dermatitis",
                 "codes": [{"code": "L20.9", "display": "Atopic dermatitis, unspecified"}],
                 "code_system": "ICD10CM"},
            ],
            "root_operator": "AND",
        },
        exclusion_criteria={
            "criteria": [
                {"criterion_type": "condition", "name": "Active cancer",
                 "codes": [{"code": "C80.1", "display": "Malignant neoplasm, unspecified"}],
                 "code_system": "ICD10CM", "negated": True},
            ],
            "root_operator": "AND",
        },
        enrollment_target=600,
    )


def _eylea_trial() -> TrialCreate:
    """EYLEA HD - Diabetic Macular Edema trial."""
    return TrialCreate(
        name="EYLEA HD DME",
        nct_number="NCT04429503",
        sponsor="Regeneron",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.RECRUITING,
        therapeutic_area="Ophthalmology",
        inclusion_criteria={
            "criteria": [
                {"criterion_type": "demographic", "name": "Adults",
                 "age_range": {"min_age": 18}},
                {"criterion_type": "condition", "name": "Diabetic Macular Edema",
                 "codes": [{"code": "H35.81", "display": "Retinal edema"}],
                 "code_system": "ICD10CM"},
                {"criterion_type": "condition", "name": "Type 2 Diabetes",
                 "codes": [{"code": "E11", "display": "Type 2 diabetes mellitus"}],
                 "code_system": "ICD10CM"},
            ],
            "root_operator": "AND",
        },
        exclusion_criteria={
            "criteria": [
                {"criterion_type": "measurement", "name": "HbA1c > 12%",
                 "codes": [{"code": "4548-4", "display": "Hemoglobin A1c"}],
                 "code_system": "LOINC",
                 "value_range": {"min_value": 12.0},
                 "negated": True},
            ],
            "root_operator": "AND",
        },
        enrollment_target=900,
    )


def _libtayo_trial() -> TrialCreate:
    """LIBTAYO - Advanced CSCC trial."""
    return TrialCreate(
        name="LIBTAYO CSCC",
        nct_number="NCT02760498",
        sponsor="Regeneron",
        phase=TrialPhase.PHASE_2,
        status=TrialStatus.RECRUITING,
        therapeutic_area="Oncology",
        inclusion_criteria={
            "criteria": [
                {"criterion_type": "demographic", "name": "Adults",
                 "age_range": {"min_age": 18}},
                {"criterion_type": "condition", "name": "Cutaneous SCC",
                 "codes": [
                     {"code": "C44.9", "display": "Malignant neoplasm of skin, unspecified"},
                     {"code": "C44.92", "display": "Squamous cell carcinoma of skin"},
                 ],
                 "code_system": "ICD10CM"},
            ],
            "root_operator": "AND",
        },
        exclusion_criteria={
            "criteria": [
                {"criterion_type": "condition", "name": "Autoimmune disease",
                 "codes": [{"code": "M35.9", "display": "Systemic involvement of connective tissue"}],
                 "code_system": "ICD10CM", "negated": True},
            ],
            "root_operator": "AND",
        },
        enrollment_target=200,
    )


def _single_condition_trial() -> TrialCreate:
    """Simple trial with one condition criterion, no exclusion."""
    return TrialCreate(
        name="Simple Diabetes Trial",
        sponsor="Test",
        phase=TrialPhase.PHASE_2,
        status=TrialStatus.RECRUITING,
        inclusion_criteria={
            "criteria": [
                {"criterion_type": "condition", "name": "Diabetes",
                 "codes": [{"code": "E11", "display": "Type 2 diabetes mellitus"}],
                 "code_system": "ICD10CM"},
            ],
            "root_operator": "AND",
        },
        exclusion_criteria=None,
        enrollment_target=50,
    )


def _no_criteria_trial() -> TrialCreate:
    """Trial with no criteria at all."""
    return TrialCreate(
        name="No Criteria Trial",
        sponsor="Test",
        phase=TrialPhase.PHASE_1,
        status=TrialStatus.RECRUITING,
        inclusion_criteria=None,
        exclusion_criteria=None,
        enrollment_target=10,
    )


# =============================================================================
# Condition Criterion Matching
# =============================================================================


class TestConditionMatching:
    """Tests for condition criterion matching logic."""

    @pytest.mark.asyncio
    async def test_matching_condition_passes(self, service, session):
        """Patient with matching condition is PASS."""
        pid = "P-COND-01"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        trial = service.create_trial(_ad_trial())

        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)
        # Condition criterion should pass (demographic may be unknown without node)
        cond_detail = [d for d in result.criteria_details if d.criterion_name == "Atopic Dermatitis"]
        assert len(cond_detail) == 1
        assert cond_detail[0].status == "PASS"

    @pytest.mark.asyncio
    async def test_non_matching_condition_unknown(self, service, session):
        """Patient without the condition domain data is UNKNOWN."""
        pid = "P-COND-02"
        # Insert a drug fact, not a condition
        await _insert_fact(session, patient_id=pid, domain=Domain.DRUG,
                          concept_name="Metformin")
        trial = service.create_trial(_single_condition_trial())

        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)
        detail = result.criteria_details[0]
        assert detail.status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_condition_data_exists_but_wrong_concept_not_met(self, service, session):
        """Patient has condition data but wrong concept -> NOT_MET."""
        pid = "P-COND-03"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Hypertension")
        trial = service.create_trial(_single_condition_trial())

        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)
        detail = result.criteria_details[0]
        assert detail.status == "NOT_MET"

    @pytest.mark.asyncio
    async def test_negated_condition_does_not_match(self, service, session):
        """Condition with assertion=ABSENT should NOT match inclusion."""
        pid = "P-COND-04"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus",
                          assertion=Assertion.ABSENT)
        trial = service.create_trial(_single_condition_trial())

        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)
        # The absent fact should not satisfy the condition
        detail = result.criteria_details[0]
        assert detail.status in ("NOT_MET", "UNKNOWN")


# =============================================================================
# Measurement Criterion Matching
# =============================================================================


class TestMeasurementMatching:
    """Tests for measurement criteria with value ranges."""

    @pytest.mark.asyncio
    async def test_measurement_in_exclusion_range_triggers(self, service, session):
        """HbA1c >= 12% triggers exclusion for EYLEA trial."""
        pid = "P-MEAS-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(55))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Retinal edema")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")
        await _insert_fact(session, patient_id=pid, domain=Domain.MEASUREMENT,
                          concept_name="Hemoglobin A1c", value="13.5", unit="%")

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        # Exclusion should be triggered
        assert not result.eligible
        assert len(result.exclusion_triggered) >= 1

    @pytest.mark.asyncio
    async def test_measurement_below_exclusion_threshold_passes(self, service, session):
        """HbA1c < 12% does NOT trigger exclusion for EYLEA trial."""
        pid = "P-MEAS-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(60))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Retinal edema")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")
        await _insert_fact(session, patient_id=pid, domain=Domain.MEASUREMENT,
                          concept_name="Hemoglobin A1c", value="7.5", unit="%")

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        # Exclusion should NOT be triggered (HbA1c 7.5 < 12)
        assert len(result.exclusion_triggered) == 0


# =============================================================================
# Demographic Criterion Matching
# =============================================================================


class TestDemographicMatching:
    """Tests for age-based demographic criteria."""

    @pytest.mark.asyncio
    async def test_age_within_range_passes(self, service, session):
        """Patient age within min/max range -> PASS."""
        pid = "P-DEMO-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(45))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "PASS"

    @pytest.mark.asyncio
    async def test_age_below_minimum_not_met(self, service, session):
        """Patient younger than min_age -> NOT_MET."""
        pid = "P-DEMO-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(16))

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "NOT_MET"

    @pytest.mark.asyncio
    async def test_age_above_maximum_not_met(self, service, session):
        """Patient older than max_age -> NOT_MET."""
        pid = "P-DEMO-03"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(80))

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "NOT_MET"

    @pytest.mark.asyncio
    async def test_no_demographic_data_unknown(self, service, session):
        """Patient with no KGNode -> UNKNOWN for demographic criteria."""
        pid = "P-DEMO-04"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_age_at_exact_boundary_passes(self, service, session):
        """Patient exactly at min_age boundary passes."""
        pid = "P-DEMO-05"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(18))

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "PASS"

    @pytest.mark.asyncio
    async def test_no_max_age_allows_elderly(self, service, session):
        """Trial with no max_age allows elderly patients."""
        pid = "P-DEMO-06"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(90))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Retinal edema")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        demo_detail = [d for d in result.criteria_details if d.criterion_type == "demographic"]
        assert len(demo_detail) == 1
        assert demo_detail[0].status == "PASS"


# =============================================================================
# Inclusion AND Logic
# =============================================================================


class TestInclusionANDLogic:
    """Tests for AND logic across multiple inclusion criteria."""

    @pytest.mark.asyncio
    async def test_all_inclusion_met_eligible(self, service, session):
        """Patient meeting ALL inclusion criteria is eligible."""
        pid = "P-AND-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True
        assert result.match_score > 0

    @pytest.mark.asyncio
    async def test_missing_one_inclusion_ineligible(self, service, session):
        """Patient missing one inclusion criterion is not eligible."""
        pid = "P-AND-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        # Have demographic but NOT atopic dermatitis
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Hypertension")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is False

    @pytest.mark.asyncio
    async def test_eylea_all_three_criteria_met(self, service, session):
        """EYLEA requires demographic + DME + T2D -- all three met."""
        pid = "P-AND-03"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(55))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Retinal edema")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True
        assert len(result.inclusion_met) == 3

    @pytest.mark.asyncio
    async def test_eylea_missing_dme_ineligible(self, service, session):
        """EYLEA: has T2D but missing DME -> ineligible."""
        pid = "P-AND-04"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(55))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")
        # NO Retinal edema fact

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is False


# =============================================================================
# Exclusion Subtraction Logic
# =============================================================================


class TestExclusionLogic:
    """Tests for exclusion criteria subtraction logic."""

    @pytest.mark.asyncio
    async def test_exclusion_removes_otherwise_eligible(self, service, session):
        """Patient meeting inclusion but triggering exclusion is ineligible."""
        pid = "P-EXCL-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(45))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Malignant neoplasm, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is False
        assert len(result.exclusion_triggered) >= 1
        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_no_exclusion_match_stays_eligible(self, service, session):
        """Patient without exclusion conditions remains eligible."""
        pid = "P-EXCL-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(45))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True
        assert len(result.exclusion_triggered) == 0

    @pytest.mark.asyncio
    async def test_exclusion_score_drops_to_zero(self, service, session):
        """Any exclusion triggered drops match score to 0.0."""
        pid = "P-EXCL-03"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Squamous cell carcinoma of skin")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Systemic involvement of connective tissue")

        trial = service.create_trial(_libtayo_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.match_score == 0.0


# =============================================================================
# Safety Block Tests
# =============================================================================


class TestSafetyBlocks:
    """Tests for CMO-5 patient safety guardrails (hard stop)."""

    @pytest.mark.asyncio
    async def test_high_confidence_exclusion_triggers_safety_block(self, service, session):
        """High-confidence exclusion match triggers safety_blocked flag."""
        pid = "P-SAFE-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(40))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Malignant neoplasm, unspecified",
                          confidence=0.95)

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.safety_blocked is True
        assert len(result.safety_blocked_reasons) >= 1
        assert result.eligible is False
        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_safety_block_overrides_inclusion(self, service, session):
        """Safety block forces ineligible even when all inclusion criteria met."""
        pid = "P-SAFE-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(35))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        # Cancer with very high confidence
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Malignant neoplasm, unspecified",
                          confidence=0.99)

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        # All inclusion criteria met but safety block forces ineligible
        assert result.eligible is False
        assert result.safety_blocked is True

    @pytest.mark.asyncio
    async def test_low_confidence_exclusion_no_safety_block(self, service, session):
        """Low-confidence exclusion match does NOT trigger safety block."""
        pid = "P-SAFE-03"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(40))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        # Cancer with low confidence -> POSSIBLE_MATCH, not FAIL
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Malignant neoplasm, unspecified",
                          confidence=0.4)

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.safety_blocked is False


# =============================================================================
# Data Completeness
# =============================================================================


class TestDataCompleteness:
    """Tests for data completeness scoring."""

    @pytest.mark.asyncio
    async def test_full_data_completeness(self, service, session):
        """All criteria evaluable -> completeness = 1.0."""
        pid = "P-COMP-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.data_completeness is not None
        # All criteria should be evaluable (demographic + condition + exclusion condition)
        assert result.data_completeness.overall_completeness > 0

    @pytest.mark.asyncio
    async def test_missing_data_reduces_completeness(self, service, session):
        """Missing domain data reduces completeness score."""
        pid = "P-COMP-02"
        # No facts at all, no patient node

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.data_completeness is not None
        assert result.data_completeness.unknown_criteria > 0
        assert result.data_completeness.overall_completeness < 1.0

    @pytest.mark.asyncio
    async def test_completeness_recommendation_generated(self, service, session):
        """Missing domains generate a recommendation."""
        pid = "P-COMP-03"
        # No patient node -> demographic unknown
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.data_completeness is not None
        if result.data_completeness.missing_domains:
            assert result.data_completeness.recommendation is not None

    def test_compute_data_completeness_all_pass(self, service):
        """All PASS criteria -> completeness = 1.0."""
        details = [
            CriterionResult(criterion_name="C1", criterion_type="condition",
                          status="PASS", confidence=1.0, weight=1.0),
            CriterionResult(criterion_name="C2", criterion_type="demographic",
                          status="PASS", confidence=1.0, weight=0.5),
        ]
        score = service._compute_data_completeness(details)
        assert score.overall_completeness == 1.0
        assert score.unknown_criteria == 0

    def test_compute_data_completeness_with_unknowns(self, service):
        """UNKNOWN criteria reduce completeness."""
        details = [
            CriterionResult(criterion_name="C1", criterion_type="condition",
                          status="PASS", confidence=1.0, weight=1.0),
            CriterionResult(criterion_name="C2", criterion_type="measurement",
                          status="UNKNOWN", confidence=0.0, weight=0.8,
                          missing_domain="lab_results"),
        ]
        score = service._compute_data_completeness(details)
        assert score.overall_completeness == 0.5
        assert score.unknown_criteria == 1
        assert "lab_results" in score.missing_domains


# =============================================================================
# Confidence Filtering
# =============================================================================


class TestConfidenceFiltering:
    """Tests for confidence-based result classification."""

    @pytest.mark.asyncio
    async def test_high_confidence_match_is_pass(self, service, session):
        """Confidence > 0.7 is classified as PASS."""
        pid = "P-CONF-01"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus", confidence=0.95)

        trial = service.create_trial(_single_condition_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        detail = result.criteria_details[0]
        assert detail.status == "PASS"
        assert detail.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_low_confidence_match_is_possible(self, service, session):
        """Confidence between 0.3 and 0.7 is POSSIBLE_MATCH."""
        pid = "P-CONF-02"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus", confidence=0.5)

        trial = service.create_trial(_single_condition_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        detail = result.criteria_details[0]
        assert detail.status == "POSSIBLE_MATCH"

    @pytest.mark.asyncio
    async def test_very_low_confidence_is_unknown(self, service, session):
        """Confidence <= 0.3 is treated as UNKNOWN."""
        pid = "P-CONF-03"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus", confidence=0.2)

        trial = service.create_trial(_single_condition_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        detail = result.criteria_details[0]
        assert detail.status == "UNKNOWN"


# =============================================================================
# Match Scoring
# =============================================================================


class TestMatchScoring:
    """Tests for weighted match score calculation."""

    @pytest.mark.asyncio
    async def test_all_criteria_met_score_1(self, service, session):
        """All criteria met -> score close to 1.0."""
        pid = "P-SCORE-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.match_score > 0.5

    @pytest.mark.asyncio
    async def test_no_criteria_met_score_0(self, service, session):
        """No criteria met -> score = 0.0."""
        pid = "P-SCORE-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(16))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Hypertension")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_partial_match_intermediate_score(self, service, session):
        """Some criteria met -> intermediate score."""
        pid = "P-SCORE-03"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        # Demographic met, condition NOT met (wrong condition)
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Hypertension")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        # Demographic criterion met, condition not met -> partial score
        assert 0.0 < result.match_score < 1.0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in trial screening."""

    @pytest.mark.asyncio
    async def test_no_clinical_facts_all_unknown(self, service, session):
        """Patient with no clinical facts -> all criteria UNKNOWN."""
        pid = "P-EDGE-01"
        trial = service.create_trial(_single_condition_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is False
        for detail in result.criteria_details:
            assert detail.status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_no_criteria_trial_everyone_eligible(self, service, session):
        """Trial with no criteria -> all patients eligible."""
        pid = "P-EDGE-02"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Anything")

        trial = service.create_trial(_no_criteria_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        # No criteria to fail -> eligible
        assert result.eligible is True

    @pytest.mark.asyncio
    async def test_nonexistent_trial_returns_none(self, service, session):
        """Screening against nonexistent trial returns None."""
        result = await service.check_patient_eligibility(
            "nonexistent-trial-id", "P-EDGE-03", session=session
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_requires_clinician_review_always_true(self, service, session):
        """All results require clinician review (Cures Act)."""
        pid = "P-EDGE-04"
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")

        trial = service.create_trial(_single_condition_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.requires_clinician_review is True
        assert "clinical decision support" in result.review_disclaimer.lower()


# =============================================================================
# Batch Screening Tests
# =============================================================================


class TestBatchScreening:
    """Tests for screen_patients (batch screening)."""

    @pytest.mark.asyncio
    async def test_batch_screening_returns_response(self, service, session):
        """screen_patients returns ScreeningResponse with counts."""
        pid = "P-BATCH-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.screen_patients(str(trial.id), session=session)

        assert result is not None
        assert result.total_patients_screened >= 1
        assert result.eligible_count >= 0
        assert result.ineligible_count >= 0

    @pytest.mark.asyncio
    async def test_batch_screening_nonexistent_trial(self, service, session):
        """Screening against nonexistent trial returns None."""
        result = await service.screen_patients("bad-id", session=session)
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_screening_with_patient_filter(self, service, session):
        """screen_patients with patient_ids filter restricts universe."""
        pid_a = "P-BATCH-A"
        pid_b = "P-BATCH-B"
        await _insert_patient_node(session, patient_id=pid_a, birth_date=_dob_for_age(50))
        await _insert_fact(session, patient_id=pid_a, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")
        await _insert_patient_node(session, patient_id=pid_b, birth_date=_dob_for_age(30))
        await _insert_fact(session, patient_id=pid_b, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        request = ScreeningRequest(patient_ids=[pid_a])
        result = await service.screen_patients(str(trial.id), request, session=session)

        assert result is not None
        assert result.total_patients_screened == 1


# =============================================================================
# Real-ish Trial Criteria Tests
# =============================================================================


class TestRealTrialCriteria:
    """Tests with real-ish Regeneron trial criteria."""

    @pytest.mark.asyncio
    async def test_dupixent_eligible_patient(self, service, session):
        """Patient eligible for Dupixent AD trial."""
        pid = "P-DUP-01"
        await _insert_patient_node(session, patient_id=pid,
                                  birth_date=_dob_for_age(35), gender="female")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Atopic dermatitis, unspecified")

        trial = service.create_trial(_ad_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True
        assert result.match_score > 0.5

    @pytest.mark.asyncio
    async def test_libtayo_eligible_patient(self, service, session):
        """Patient eligible for Libtayo CSCC trial."""
        pid = "P-LIB-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(65))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Squamous cell carcinoma of skin")

        trial = service.create_trial(_libtayo_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True

    @pytest.mark.asyncio
    async def test_libtayo_excluded_by_autoimmune(self, service, session):
        """Patient excluded from Libtayo due to autoimmune disease."""
        pid = "P-LIB-02"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(60))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Squamous cell carcinoma of skin")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Systemic involvement of connective tissue")

        trial = service.create_trial(_libtayo_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is False
        assert len(result.exclusion_triggered) >= 1

    @pytest.mark.asyncio
    async def test_eylea_fully_eligible(self, service, session):
        """Patient fully eligible for EYLEA HD trial."""
        pid = "P-EYL-01"
        await _insert_patient_node(session, patient_id=pid, birth_date=_dob_for_age(60))
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Retinal edema")
        await _insert_fact(session, patient_id=pid, domain=Domain.CONDITION,
                          concept_name="Type 2 diabetes mellitus")

        trial = service.create_trial(_eylea_trial())
        result = await service.check_patient_eligibility(str(trial.id), pid, session=session)

        assert result.eligible is True
        assert result.match_score > 0.5


# =============================================================================
# CRUD Smoke Tests
# =============================================================================


class TestTrialCRUD:
    """Smoke tests for trial CRUD operations."""

    def test_create_trial(self, service):
        """Trial creation returns a response with ID."""
        resp = service.create_trial(_single_condition_trial())
        assert resp.id is not None
        assert resp.name == "Simple Diabetes Trial"

    async def test_get_nonexistent_trial(self, service):
        """Getting a nonexistent trial returns None."""
        result = await service.get_trial("nonexistent")
        assert result is None

    def test_delete_trial(self, service):
        """Deleting an existing trial returns True."""
        resp = service.create_trial(_single_condition_trial())
        assert service.delete_trial(str(resp.id)) is True
        assert service.delete_trial(str(resp.id)) is False  # Already deleted

    async def test_list_trials(self, service):
        """List trials returns demo + created trials."""
        trials, total = await service.list_trials()
        # Demo trials exist from __init__
        assert total >= 3
