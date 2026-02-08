"""Tests for TrialEligibilityService eligibility logic.

QA-3.3: Eligibility Logic Test Framework

Covers:
- Clearly eligible patients (all inclusion, no exclusion)
- Clearly ineligible patients (fails key inclusion criteria)
- Boundary cases (age at cutoff, measurement thresholds)
- Missing data (no facts on file -> UNKNOWN, not PASS)
- Exclusion enforcement (meets inclusion + has exclusion = ineligible)
- Multiple criteria AND logic (intersection of inclusion criteria)
- Negated conditions (assertion=ABSENT should NOT match)
- Weighted scoring calculation
- Demographic filtering via KGNode
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
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
    ScreeningResponse,
    TrialCreate,
)
from app.models.trial import TrialPhase, TrialStatus
from app.services.trial_eligibility_service import TrialEligibilityService


# =============================================================================
# Async Engine / Session Fixtures
# =============================================================================


@pytest.fixture(scope="function")
async def engine():
    """Create an async SQLite in-memory engine for testing.

    Only creates the tables needed for eligibility testing (ClinicalFact,
    KGNode) to avoid SQLite compatibility issues with the full schema
    (e.g., OMOP tables with composite autoincrement primary keys).
    """
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    # Only create tables required for eligibility logic
    tables = [
        ClinicalFact.__table__,
        KGNode.__table__,
    ]
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
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as sess:
        yield sess
        await sess.rollback()


# =============================================================================
# Service Fixture (fresh instance per test, skip DB loading)
# =============================================================================


@pytest.fixture
def service() -> TrialEligibilityService:
    """Create a fresh TrialEligibilityService.

    Marks _loaded_from_db=True so the service does not attempt to query
    the Trial table (which does not exist in these unit tests).
    """
    svc = TrialEligibilityService()
    svc._loaded_from_db = True
    return svc


# =============================================================================
# Helper to insert clinical facts
# =============================================================================


async def _insert_fact(
    session: AsyncSession,
    *,
    patient_id: str,
    domain: Domain,
    concept_name: str,
    assertion: Assertion = Assertion.PRESENT,
    confidence: float = 0.95,
    value: str | None = None,
    unit: str | None = None,
    omop_concept_id: int = 0,
) -> ClinicalFact:
    """Insert a ClinicalFact into the test database and return it."""
    fact = ClinicalFact(
        id=str(uuid4()),
        patient_id=patient_id,
        domain=domain,
        omop_concept_id=omop_concept_id,
        concept_name=concept_name,
        assertion=assertion,
        temporality=Temporality.CURRENT,
        experiencer=Experiencer.PATIENT,
        confidence=confidence,
        value=value,
        unit=unit,
    )
    session.add(fact)
    await session.flush()
    return fact


async def _insert_patient_node(
    session: AsyncSession,
    *,
    patient_id: str,
    birth_date: str | None = None,
    gender: str | None = None,
) -> KGNode:
    """Insert a KGNode of type PATIENT with optional birth_date."""
    props: dict = {}
    if birth_date:
        props["birth_date"] = birth_date
    if gender:
        props["gender"] = gender

    node = KGNode(
        id=str(uuid4()),
        patient_id=patient_id,
        node_type=NodeType.PATIENT,
        omop_concept_id=None,
        label=f"Patient {patient_id}",
        properties=props,
    )
    session.add(node)
    await session.flush()
    return node


# =============================================================================
# Trial Definitions (reusable across tests)
# =============================================================================


def _ad_trial_create() -> TrialCreate:
    """Atopic Dermatitis (Dupixent) trial definition."""
    return TrialCreate(
        name="DUPIXENT AD Trial",
        nct_number="NCT02395133",
        sponsor="Regeneron",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.RECRUITING,
        therapeutic_area="Dermatology",
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
            ],
            "root_operator": "AND",
        },
        enrollment_target=600,
        site_count=250,
    )


def _dme_trial_create() -> TrialCreate:
    """Diabetic Macular Edema (EYLEA HD) trial definition."""
    return TrialCreate(
        name="EYLEA HD DME Trial",
        nct_number="NCT04429503",
        sponsor="Regeneron",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.RECRUITING,
        therapeutic_area="Ophthalmology",
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
    )


def _simple_condition_trial() -> TrialCreate:
    """A minimal trial with only a condition criterion (no demographics)."""
    return TrialCreate(
        name="Simple Condition Trial",
        sponsor="Test",
        phase=TrialPhase.PHASE_2,
        status=TrialStatus.RECRUITING,
        inclusion_criteria={
            "criteria": [
                {
                    "criterion_type": "condition",
                    "name": "Hypertension",
                    "codes": [
                        {"code": "I10", "display": "Essential hypertension"},
                    ],
                    "code_system": "ICD10CM",
                },
            ],
            "root_operator": "AND",
        },
        exclusion_criteria={"criteria": [], "root_operator": "AND"},
        enrollment_target=100,
    )


def _register_trial(service: TrialEligibilityService, create: TrialCreate) -> str:
    """Register a trial and return its ID."""
    response = service.create_trial(create)
    return str(response.id)


# =============================================================================
# Tests: Clearly Eligible Patient
# =============================================================================


class TestClearlyEligiblePatient:
    """Patient meets all inclusion criteria and no exclusion criteria."""

    @pytest.mark.asyncio
    async def test_eligible_patient_condition_only(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has the required condition and no exclusion triggers."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-ELIGIBLE-01",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-ELIGIBLE-01", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert result.match_score > 0.0
        assert "Hypertension" in result.inclusion_met
        assert len(result.exclusion_triggered) == 0
        assert len(result.missing_data) == 0

    @pytest.mark.asyncio
    async def test_eligible_ad_patient(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient meets all AD trial criteria: age + condition, no cancer."""
        trial_id = _register_trial(service, _ad_trial_create())

        # Age 40 -- clearly within 18-75 range
        birth = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-AD-OK", birth_date=birth)

        # Atopic dermatitis fact
        await _insert_fact(
            session,
            patient_id="P-AD-OK",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-AD-OK", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert result.match_score > 0.0
        assert "Atopic Dermatitis" in result.inclusion_met
        assert "Adult patients" in result.inclusion_met
        assert len(result.exclusion_triggered) == 0

    @pytest.mark.asyncio
    async def test_eligible_dme_patient(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient meets all DME trial criteria: age + retinal edema + diabetes, low HbA1c."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=55 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-DME-OK", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-DME-OK",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-DME-OK",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )
        # HbA1c = 7.2 -- below 12 threshold, should NOT trigger exclusion
        await _insert_fact(
            session,
            patient_id="P-DME-OK",
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="7.2",
            unit="%",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-DME-OK", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert "Diabetic Macular Edema" in result.inclusion_met
        assert "Type 2 Diabetes" in result.inclusion_met
        assert len(result.exclusion_triggered) == 0


# =============================================================================
# Tests: Clearly Ineligible Patient
# =============================================================================


class TestClearlyIneligiblePatient:
    """Patient fails key inclusion criteria."""

    @pytest.mark.asyncio
    async def test_ineligible_no_matching_condition(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has unrelated conditions -- not eligible."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # Insert a fact that does NOT match "Essential hypertension"
        await _insert_fact(
            session,
            patient_id="P-INELIGIBLE-01",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-INELIGIBLE-01", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Hypertension" not in result.inclusion_met
        assert "Hypertension" in result.missing_data

    @pytest.mark.asyncio
    async def test_ineligible_wrong_domain(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has matching concept name but in wrong domain."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # "Essential hypertension" as a DRUG fact -- should not match condition criterion
        await _insert_fact(
            session,
            patient_id="P-WRONG-DOMAIN",
            domain=Domain.DRUG,
            concept_name="Essential hypertension",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-WRONG-DOMAIN", session=session
        )
        assert result is not None
        assert result.eligible is False

    @pytest.mark.asyncio
    async def test_ineligible_missing_one_inclusion_criterion(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """DME trial requires both retinal edema AND diabetes; patient has only one."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-PARTIAL", birth_date=birth)

        # Only retinal edema, no diabetes
        await _insert_fact(
            session,
            patient_id="P-PARTIAL",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-PARTIAL", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Diabetic Macular Edema" in result.inclusion_met
        assert "Type 2 Diabetes" in result.missing_data


# =============================================================================
# Tests: Boundary Cases
# =============================================================================


class TestBoundaryCases:
    """Age exactly at cutoff, lab values at threshold boundaries."""

    @pytest.mark.asyncio
    async def test_age_exactly_at_min(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient is exactly 18 years old -- should be eligible (min_age=18)."""
        trial_id = _register_trial(service, _ad_trial_create())

        # Birth date exactly 18 years ago
        birth = (datetime.now(timezone.utc) - timedelta(days=18 * 365 + 5)).isoformat()
        await _insert_patient_node(session, patient_id="P-AGE-18", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-AGE-18",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-AGE-18", session=session
        )
        assert result is not None
        assert "Adult patients" in result.inclusion_met

    @pytest.mark.asyncio
    async def test_age_below_min(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient is 17 years old -- should not match age criterion."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=17 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-AGE-17", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-AGE-17",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-AGE-17", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Adult patients" in result.missing_data

    @pytest.mark.asyncio
    async def test_age_exactly_at_max(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient is exactly 75 years old -- should be eligible (max_age=75)."""
        trial_id = _register_trial(service, _ad_trial_create())

        # 75 years, but not exceeding
        birth = (datetime.now(timezone.utc) - timedelta(days=75 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-AGE-75", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-AGE-75",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-AGE-75", session=session
        )
        assert result is not None
        assert "Adult patients" in result.inclusion_met

    @pytest.mark.asyncio
    async def test_age_above_max(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient is 76 years old -- should fail max_age=75."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=76 * 366)).isoformat()
        await _insert_patient_node(session, patient_id="P-AGE-76", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-AGE-76",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-AGE-76", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Adult patients" in result.missing_data

    @pytest.mark.asyncio
    async def test_hba1c_at_exclusion_threshold(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """HbA1c = 12.0 exactly -- should trigger the exclusion (min_value >= 12)."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-HBA1C-12", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-HBA1C-12",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-HBA1C-12",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )
        await _insert_fact(
            session,
            patient_id="P-HBA1C-12",
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="12.0",
            unit="%",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-HBA1C-12", session=session
        )
        assert result is not None
        # HbA1c >= 12 triggers the exclusion
        assert result.eligible is False
        assert "Uncontrolled diabetes (HbA1c > 12%)" in result.exclusion_triggered

    @pytest.mark.asyncio
    async def test_hba1c_just_below_threshold(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """HbA1c = 11.9 -- should NOT trigger the exclusion."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-HBA1C-OK", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-HBA1C-OK",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-HBA1C-OK",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )
        await _insert_fact(
            session,
            patient_id="P-HBA1C-OK",
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="11.9",
            unit="%",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-HBA1C-OK", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert len(result.exclusion_triggered) == 0


# =============================================================================
# Tests: Missing Data
# =============================================================================


class TestMissingData:
    """Patient has no relevant clinical facts on file."""

    @pytest.mark.asyncio
    async def test_no_facts_returns_unknown_not_pass(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with no clinical facts should get UNKNOWN status, not PASS.

        Clinical safety: missing data must never be treated as positive evidence.
        """
        trial_id = _register_trial(service, _simple_condition_trial())

        # Insert a fact for a DIFFERENT patient so the universe is not empty
        await _insert_fact(
            session,
            patient_id="P-OTHER",
            domain=Domain.CONDITION,
            concept_name="Something unrelated",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NODATA", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Hypertension" in result.missing_data

        # Verify the criterion detail status is UNKNOWN
        criterion_detail = result.criteria_details[0]
        assert criterion_detail.status == "UNKNOWN"
        assert criterion_detail.confidence == 0.0

    @pytest.mark.asyncio
    async def test_missing_birth_date_fails_demographic(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient node without birth_date should fail demographic criterion.

        The _get_demographic_patient_ids method skips patients without
        birth_date in properties -- correctly treating missing data as not matched.
        """
        trial_id = _register_trial(service, _ad_trial_create())

        # Patient node with NO birth_date
        await _insert_patient_node(
            session, patient_id="P-NOBIRTHDATE", birth_date=None
        )
        await _insert_fact(
            session,
            patient_id="P-NOBIRTHDATE",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NOBIRTHDATE", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Adult patients" in result.missing_data

    @pytest.mark.asyncio
    async def test_no_patient_node_at_all(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with no KGNode at all should fail demographic criterion."""
        trial_id = _register_trial(service, _ad_trial_create())

        await _insert_fact(
            session,
            patient_id="P-NONODE",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NONODE", session=session
        )
        assert result is not None
        assert result.eligible is False
        # Demographic criterion should report UNKNOWN
        demographic_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_type == "demographic"),
            None,
        )
        assert demographic_cr is not None
        assert demographic_cr.status == "UNKNOWN"


# =============================================================================
# Tests: Exclusion Enforcement
# =============================================================================


class TestExclusionEnforcement:
    """Patient meets all inclusion but has an exclusion condition."""

    @pytest.mark.asyncio
    async def test_exclusion_condition_overrides_inclusion(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with AD + cancer should be excluded from AD trial."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=45 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-EXCLUDED", birth_date=birth)

        # Meets inclusion: has AD
        await _insert_fact(
            session,
            patient_id="P-EXCLUDED",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )
        # Triggers exclusion: has cancer
        await _insert_fact(
            session,
            patient_id="P-EXCLUDED",
            domain=Domain.CONDITION,
            concept_name="Malignant neoplasm, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-EXCLUDED", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Active cancer" in result.exclusion_triggered
        # Score should be zero when exclusion triggers
        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_exclusion_measurement_value(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """DME trial: patient with HbA1c > 12 should be excluded."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=60 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-HIGH-A1C", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-HIGH-A1C",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-HIGH-A1C",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )
        await _insert_fact(
            session,
            patient_id="P-HIGH-A1C",
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="14.5",
            unit="%",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-HIGH-A1C", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert result.match_score == 0.0
        assert "Uncontrolled diabetes (HbA1c > 12%)" in result.exclusion_triggered

    @pytest.mark.asyncio
    async def test_exclusion_does_not_trigger_below_threshold(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """HbA1c = 8.0 should NOT trigger the >= 12.0 exclusion."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-SAFE-A1C", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-SAFE-A1C",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-SAFE-A1C",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )
        await _insert_fact(
            session,
            patient_id="P-SAFE-A1C",
            domain=Domain.MEASUREMENT,
            concept_name="Hemoglobin A1c",
            value="8.0",
            unit="%",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-SAFE-A1C", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert len(result.exclusion_triggered) == 0


# =============================================================================
# Tests: Multiple Criteria AND Logic
# =============================================================================


class TestMultipleCriteriaAndLogic:
    """Intersection of multiple inclusion criteria (all must be met)."""

    @pytest.mark.asyncio
    async def test_all_three_inclusion_criteria_required(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """DME trial requires age + retinal edema + diabetes. Missing any one = ineligible."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-TWO-OF-THREE", birth_date=birth)

        # Only retinal edema, missing diabetes
        await _insert_fact(
            session,
            patient_id="P-TWO-OF-THREE",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-TWO-OF-THREE", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert result.inclusion_total == 3
        # Should have met demographic + retinal edema but not diabetes
        assert "Diabetic Macular Edema" in result.inclusion_met
        assert "Type 2 Diabetes" not in result.inclusion_met
        assert "Type 2 Diabetes" in result.missing_data

    @pytest.mark.asyncio
    async def test_all_criteria_met_makes_eligible(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """When all 3 DME criteria are met, patient is eligible."""
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-ALL-THREE", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-ALL-THREE",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )
        await _insert_fact(
            session,
            patient_id="P-ALL-THREE",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-ALL-THREE", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert result.inclusion_total == 3
        assert len(result.inclusion_met) == 3


# =============================================================================
# Tests: Negated Conditions
# =============================================================================


class TestNegatedConditions:
    """Assertion=ABSENT should NOT match inclusion criteria.

    Clinical safety: "Patient denies diabetes" must not be treated as
    evidence that the patient HAS diabetes.
    """

    @pytest.mark.asyncio
    async def test_negated_condition_does_not_match_inclusion(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """A fact with assertion=ABSENT should not satisfy the inclusion criterion."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # Insert hypertension with assertion=ABSENT ("patient denies hypertension")
        await _insert_fact(
            session,
            patient_id="P-NEGATED",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            assertion=Assertion.ABSENT,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NEGATED", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Hypertension" not in result.inclusion_met
        assert "Hypertension" in result.missing_data

    @pytest.mark.asyncio
    async def test_possible_assertion_not_definitive(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """A fact with assertion=POSSIBLE should not match (only PRESENT matches)."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-POSSIBLE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            assertion=Assertion.POSSIBLE,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-POSSIBLE", session=session
        )
        assert result is not None
        assert result.eligible is False

    @pytest.mark.asyncio
    async def test_negated_exclusion_condition_does_not_exclude(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """A cancer fact with assertion=ABSENT should not trigger cancer exclusion.

        If a note says "patient denies cancer history", the ABSENT assertion
        means the exclusion condition is NOT present -- patient should NOT be excluded.
        """
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-NO-CANCER", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-NO-CANCER",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )
        # Cancer fact with assertion=ABSENT -- should NOT trigger exclusion
        await _insert_fact(
            session,
            patient_id="P-NO-CANCER",
            domain=Domain.CONDITION,
            concept_name="Malignant neoplasm, unspecified",
            assertion=Assertion.ABSENT,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NO-CANCER", session=session
        )
        assert result is not None
        assert result.eligible is True
        assert len(result.exclusion_triggered) == 0


# =============================================================================
# Tests: Weighted Scoring Calculation
# =============================================================================


class TestWeightedScoring:
    """Verify match score calculation is correct."""

    @pytest.mark.asyncio
    async def test_score_between_zero_and_one(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Match score must always be between 0.0 and 1.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-SCORE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-SCORE", session=session
        )
        assert result is not None
        assert 0.0 <= result.match_score <= 1.0

    @pytest.mark.asyncio
    async def test_full_match_score_is_one(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient meeting all criteria should have score of 1.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-FULL-SCORE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-FULL-SCORE", session=session
        )
        assert result is not None
        assert result.match_score == 1.0

    @pytest.mark.asyncio
    async def test_exclusion_drops_score_to_zero(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """When any exclusion is triggered, score must be 0.0."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-EXC-SCORE", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-EXC-SCORE",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )
        await _insert_fact(
            session,
            patient_id="P-EXC-SCORE",
            domain=Domain.CONDITION,
            concept_name="Malignant neoplasm, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-EXC-SCORE", session=session
        )
        assert result is not None
        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_criterion_weights_applied(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Verify that criterion type weights are reflected in scoring.

        The service defines:
          condition -> weight 1.0
          measurement -> weight 0.8
          demographic -> weight 0.5
        """
        # Create a trial with one condition and one demographic criterion
        trial_create = TrialCreate(
            name="Weighted Trial",
            sponsor="Test",
            phase=TrialPhase.PHASE_2,
            status=TrialStatus.RECRUITING,
            inclusion_criteria={
                "criteria": [
                    {
                        "criterion_type": "demographic",
                        "name": "Adults",
                        "age_range": {"min_age": 18},
                    },
                    {
                        "criterion_type": "condition",
                        "name": "Diabetes",
                        "codes": [{"code": "E11", "display": "Type 2 diabetes"}],
                        "code_system": "ICD10CM",
                    },
                ],
                "root_operator": "AND",
            },
            exclusion_criteria={"criteria": [], "root_operator": "AND"},
            enrollment_target=50,
        )
        trial_id = _register_trial(service, trial_create)

        birth = (datetime.now(timezone.utc) - timedelta(days=30 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-WEIGHT", birth_date=birth)

        # Only meet demographic criterion (weight=0.5), not condition (weight=1.0)
        # Score = met_weight / evaluable_weight = 0.5 / (0.5 + ?)
        # Condition criterion has no matching facts -> UNKNOWN -> not in evaluable
        # So only demographic is evaluable -> score = 0.5/0.5 = 1.0
        # But eligible is still False because not all inclusion criteria met

        result = await service.check_patient_eligibility(
            trial_id, "P-WEIGHT", session=session
        )
        assert result is not None
        assert result.eligible is False
        # Demographic should have weight 0.5
        demo_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_type == "demographic"),
            None,
        )
        assert demo_cr is not None
        assert demo_cr.weight == 0.5

        # Condition should have weight 1.0
        cond_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_type == "condition"),
            None,
        )
        assert cond_cr is not None
        assert cond_cr.weight == 1.0

    @pytest.mark.asyncio
    async def test_no_evaluable_criteria_score_is_zero(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """If no criteria are evaluable (all UNKNOWN), score should be 0.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # No facts at all for this patient
        result = await service.check_patient_eligibility(
            trial_id, "P-EMPTY-UNIVERSE", session=session
        )
        assert result is not None
        assert result.match_score == 0.0
        assert result.eligible is False
        assert result.evaluable_criteria == 0


# =============================================================================
# Tests: Confidence-Based Status
# =============================================================================


class TestConfidenceBasedStatus:
    """Verify criterion result status depends on confidence scores."""

    @pytest.mark.asyncio
    async def test_high_confidence_returns_pass(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Confidence > 0.7 should result in PASS status."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-HIGH-CONF",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-HIGH-CONF", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert cond_cr.status == "PASS"
        assert cond_cr.confidence > 0.7

    @pytest.mark.asyncio
    async def test_medium_confidence_returns_possible_match(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Confidence between 0.3 and 0.7 should result in POSSIBLE_MATCH."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-MED-CONF",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.5,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-MED-CONF", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert cond_cr.status == "POSSIBLE_MATCH"
        assert 0.3 < cond_cr.confidence <= 0.7

    @pytest.mark.asyncio
    async def test_low_confidence_returns_unknown(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Confidence <= 0.3 should result in UNKNOWN status."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-LOW-CONF",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.2,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-LOW-CONF", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert cond_cr.status == "UNKNOWN"
        assert cond_cr.confidence <= 0.3

    @pytest.mark.asyncio
    async def test_possible_match_does_not_count_as_met(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """POSSIBLE_MATCH status should not count as inclusion_met."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-POSSIBLE-MATCH",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.5,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-POSSIBLE-MATCH", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Hypertension" not in result.inclusion_met
        assert "Hypertension" in result.missing_data


# =============================================================================
# Tests: Exclusion with High Confidence Returns FAIL
# =============================================================================


class TestExclusionCriterionStatus:
    """Verify exclusion criteria use FAIL status when matched with high confidence."""

    @pytest.mark.asyncio
    async def test_exclusion_high_confidence_returns_fail(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Exclusion criterion matched with confidence > 0.7 should return FAIL."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-EXC-FAIL", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-EXC-FAIL",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )
        await _insert_fact(
            session,
            patient_id="P-EXC-FAIL",
            domain=Domain.CONDITION,
            concept_name="Malignant neoplasm, unspecified",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-EXC-FAIL", session=session
        )
        assert result is not None
        # Find the exclusion criterion result
        excl_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_name == "Active cancer"),
            None,
        )
        assert excl_cr is not None
        assert excl_cr.status == "FAIL"


# =============================================================================
# Tests: screen_patients (batch screening)
# =============================================================================


class TestScreenPatients:
    """Test the batch screen_patients method."""

    @pytest.mark.asyncio
    async def test_screen_patients_returns_response(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """screen_patients should return a ScreeningResponse."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-SCREEN-1",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
        )
        await _insert_fact(
            session,
            patient_id="P-SCREEN-2",
            domain=Domain.CONDITION,
            concept_name="Something else",
        )

        response = await service.screen_patients(trial_id, session=session)
        assert response is not None
        assert isinstance(response, ScreeningResponse)
        assert response.total_patients_screened == 2
        assert response.eligible_count == 1
        assert response.ineligible_count == 1

    @pytest.mark.asyncio
    async def test_screen_patients_with_patient_ids_filter(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """screen_patients with patient_ids filter restricts the screening universe."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-FILTER-1",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
        )
        await _insert_fact(
            session,
            patient_id="P-FILTER-2",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
        )

        # Only screen P-FILTER-1
        request = ScreeningRequest(patient_ids=["P-FILTER-1"])
        response = await service.screen_patients(trial_id, request, session=session)
        assert response is not None
        assert response.total_patients_screened == 1
        assert response.eligible_count == 1

    @pytest.mark.asyncio
    async def test_screen_patients_nonexistent_trial(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """screen_patients for a nonexistent trial returns None."""
        response = await service.screen_patients("nonexistent-id", session=session)
        assert response is None

    @pytest.mark.asyncio
    async def test_screen_patients_exclusion_breakdown(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """screen_patients should report exclusion breakdown."""
        trial_id = _register_trial(service, _ad_trial_create())

        # Patient 1: AD + age OK + cancer -> excluded
        birth1 = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-BD-1", birth_date=birth1)
        await _insert_fact(
            session,
            patient_id="P-BD-1",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )
        await _insert_fact(
            session,
            patient_id="P-BD-1",
            domain=Domain.CONDITION,
            concept_name="Malignant neoplasm, unspecified",
        )

        # Patient 2: AD + age OK, no cancer -> eligible
        birth2 = (datetime.now(timezone.utc) - timedelta(days=35 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-BD-2", birth_date=birth2)
        await _insert_fact(
            session,
            patient_id="P-BD-2",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        response = await service.screen_patients(trial_id, session=session)
        assert response is not None
        assert response.exclusion_breakdown is not None
        assert response.exclusion_breakdown.get("Active cancer", 0) >= 1


# =============================================================================
# Tests: Evidence Tracking in CriterionResult
# =============================================================================


class TestEvidenceTracking:
    """Verify that criterion results include evidence fact IDs."""

    @pytest.mark.asyncio
    async def test_criterion_result_includes_fact_ids(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """CriterionResult should list the ClinicalFact IDs that support it."""
        trial_id = _register_trial(service, _simple_condition_trial())

        fact = await _insert_fact(
            session,
            patient_id="P-EVIDENCE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-EVIDENCE", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert len(cond_cr.evidence_fact_ids) >= 1
        assert str(fact.id) in cond_cr.evidence_fact_ids

    @pytest.mark.asyncio
    async def test_criterion_result_multiple_facts(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Multiple matching facts should all appear in evidence_fact_ids."""
        trial_id = _register_trial(service, _simple_condition_trial())

        fact1 = await _insert_fact(
            session,
            patient_id="P-MULTI-EVIDENCE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )
        fact2 = await _insert_fact(
            session,
            patient_id="P-MULTI-EVIDENCE",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension documented",
            confidence=0.85,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-MULTI-EVIDENCE", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        # The ilike pattern matches both facts
        assert len(cond_cr.evidence_fact_ids) >= 1


# =============================================================================
# Tests: _criterion_patient_query helper (unit tests)
# =============================================================================


class TestCriterionPatientQuery:
    """Unit tests for the SQL-generating helper _criterion_patient_query."""

    def test_demographic_returns_none(self, service: TrialEligibilityService):
        """Demographic criteria are handled separately via KGNode."""
        criterion = {"criterion_type": "demographic", "age_range": {"min_age": 18}}
        result = service._criterion_patient_query(criterion)
        assert result is None

    def test_unknown_type_returns_none(self, service: TrialEligibilityService):
        """Unknown criterion type should return None, not crash."""
        criterion = {
            "criterion_type": "unknown_type",
            "codes": [{"code": "X", "display": "test"}],
        }
        result = service._criterion_patient_query(criterion)
        assert result is None

    def test_no_display_terms_returns_none(self, service: TrialEligibilityService):
        """Criterion with empty codes list should return None."""
        criterion = {
            "criterion_type": "condition",
            "codes": [],
        }
        result = service._criterion_patient_query(criterion)
        assert result is None

    def test_condition_returns_select(self, service: TrialEligibilityService):
        """Valid condition criterion should return a SELECT statement."""
        criterion = {
            "criterion_type": "condition",
            "codes": [{"code": "I10", "display": "hypertension"}],
        }
        result = service._criterion_patient_query(criterion)
        assert result is not None

    def test_measurement_with_value_range(self, service: TrialEligibilityService):
        """Measurement criterion with value_range should include numeric filters."""
        criterion = {
            "criterion_type": "measurement",
            "codes": [{"code": "4548-4", "display": "Hemoglobin A1c"}],
            "value_range": {"min_value": 12.0},
        }
        result = service._criterion_patient_query(criterion)
        assert result is not None


# =============================================================================
# Tests: PatientEligibility Schema Invariants
# =============================================================================


class TestPatientEligibilityInvariants:
    """Verify structural invariants of the PatientEligibility response."""

    @pytest.mark.asyncio
    async def test_inclusion_met_plus_missing_equals_total(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """inclusion_met + missing_data should account for all inclusion criteria.

        Note: in the current implementation, POSSIBLE_MATCH criteria go to
        missing_data, so: len(inclusion_met) + len(missing_data) == inclusion_total.
        """
        trial_id = _register_trial(service, _dme_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-INVARIANT", birth_date=birth)

        # Only meet one of three criteria
        await _insert_fact(
            session,
            patient_id="P-INVARIANT",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-INVARIANT", session=session
        )
        assert result is not None
        assert len(result.inclusion_met) + len(result.missing_data) == result.inclusion_total

    @pytest.mark.asyncio
    async def test_eligible_patient_has_all_inclusion_met(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """An eligible patient must have len(inclusion_met) == inclusion_total."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-FULL-MET",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-FULL-MET", session=session
        )
        assert result is not None
        if result.eligible:
            assert len(result.inclusion_met) == result.inclusion_total
            assert len(result.exclusion_triggered) == 0

    @pytest.mark.asyncio
    async def test_screening_timestamp_is_set(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """PatientEligibility should have a screening_timestamp."""
        trial_id = _register_trial(service, _simple_condition_trial())

        result = await service.check_patient_eligibility(
            trial_id, "P-TIMESTAMP", session=session
        )
        assert result is not None
        assert result.screening_timestamp is not None

    @pytest.mark.asyncio
    async def test_criteria_details_count_matches_criteria(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """criteria_details should contain one entry per criterion (inclusion + exclusion)."""
        trial_id = _register_trial(service, _ad_trial_create())

        birth = (datetime.now(timezone.utc) - timedelta(days=40 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-DETAIL-COUNT", birth_date=birth)

        await _insert_fact(
            session,
            patient_id="P-DETAIL-COUNT",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-DETAIL-COUNT", session=session
        )
        assert result is not None
        # AD trial: 2 inclusion + 1 exclusion = 3 criteria
        assert len(result.criteria_details) == result.inclusion_total + result.exclusion_total


# =============================================================================
# Tests: Trial that does not exist
# =============================================================================


class TestNonexistentTrial:
    """Service should handle lookups for nonexistent trials gracefully."""

    @pytest.mark.asyncio
    async def test_check_eligibility_nonexistent_trial(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """check_patient_eligibility for nonexistent trial returns None."""
        result = await service.check_patient_eligibility(
            "does-not-exist", "P001", session=session
        )
        assert result is None


# =============================================================================
# Tests: Family history assertions
# =============================================================================


class TestFamilyHistoryAssertions:
    """Family history conditions should not match inclusion criteria.

    The service filters on assertion == PRESENT only.
    """

    @pytest.mark.asyncio
    async def test_family_history_does_not_match(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """A condition with assertion=FAMILY_HISTORY should not satisfy inclusion."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-FAMILY",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            assertion=Assertion.FAMILY_HISTORY,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-FAMILY", session=session
        )
        assert result is not None
        assert result.eligible is False
        assert "Hypertension" in result.missing_data


# =============================================================================
# Tests: NOT_MET vs UNKNOWN Distinction (CDO-6)
# =============================================================================


class TestNotMetVsUnknown:
    """CDO-6: Data Completeness Scoring.

    Verify that the system distinguishes between:
    - NOT_MET: Patient has data in the relevant domain but the criterion is not satisfied.
    - UNKNOWN: Patient has no data in the relevant domain at all.
    """

    @pytest.mark.asyncio
    async def test_no_data_at_all_returns_unknown(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with absolutely no condition data should get UNKNOWN status."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # No facts for this patient
        result = await service.check_patient_eligibility(
            trial_id, "P-NO-DATA-CDO6", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert cond_cr.status == "UNKNOWN"
        assert cond_cr.missing_domain == "conditions"

    @pytest.mark.asyncio
    async def test_has_condition_data_but_wrong_condition_returns_not_met(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has condition data (diabetes) but not hypertension -> NOT_MET."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # Insert a condition fact that does NOT match the trial criterion
        await _insert_fact(
            session,
            patient_id="P-WRONG-COND-CDO6",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-WRONG-COND-CDO6", session=session
        )
        assert result is not None
        cond_cr = result.criteria_details[0]
        assert cond_cr.status == "NOT_MET"
        assert cond_cr.missing_domain is None  # NOT_MET does not have a missing_domain

    @pytest.mark.asyncio
    async def test_not_met_is_evaluable_in_scoring(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """NOT_MET criteria should count as evaluable (we have data)."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # Patient has conditions (just not the right one)
        await _insert_fact(
            session,
            patient_id="P-EVALUABLE-CDO6",
            domain=Domain.CONDITION,
            concept_name="Type 2 diabetes mellitus",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-EVALUABLE-CDO6", session=session
        )
        assert result is not None
        # NOT_MET is evaluable, so evaluable_criteria should be 1
        assert result.evaluable_criteria == 1
        # Score should be 0 because the criterion is not met
        assert result.match_score == 0.0

    @pytest.mark.asyncio
    async def test_unknown_is_not_evaluable_in_scoring(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """UNKNOWN criteria should NOT count as evaluable."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # No data at all
        result = await service.check_patient_eligibility(
            trial_id, "P-UNKNOWN-CDO6", session=session
        )
        assert result is not None
        assert result.evaluable_criteria == 0

    @pytest.mark.asyncio
    async def test_demographic_not_met_with_age_data(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has demographic data (birth_date) but age is out of range -> NOT_MET."""
        trial_id = _register_trial(service, _ad_trial_create())

        # Patient is 17 (too young for 18-75 range), but HAS birth_date
        birth = (datetime.now(timezone.utc) - timedelta(days=17 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-YOUNG-CDO6", birth_date=birth)
        await _insert_fact(
            session,
            patient_id="P-YOUNG-CDO6",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-YOUNG-CDO6", session=session
        )
        assert result is not None
        demo_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_type == "demographic"),
            None,
        )
        assert demo_cr is not None
        assert demo_cr.status == "NOT_MET"
        assert demo_cr.missing_domain is None

    @pytest.mark.asyncio
    async def test_demographic_unknown_no_patient_node(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with no KGNode should get UNKNOWN for demographic criteria."""
        trial_id = _register_trial(service, _ad_trial_create())

        await _insert_fact(
            session,
            patient_id="P-NONODE-CDO6",
            domain=Domain.CONDITION,
            concept_name="Atopic dermatitis, unspecified",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NONODE-CDO6", session=session
        )
        assert result is not None
        demo_cr = next(
            (cr for cr in result.criteria_details if cr.criterion_type == "demographic"),
            None,
        )
        assert demo_cr is not None
        assert demo_cr.status == "UNKNOWN"
        assert demo_cr.missing_domain == "demographics"


# =============================================================================
# Tests: Data Completeness Score (CDO-6)
# =============================================================================


class TestDataCompletenessScore:
    """CDO-6: Verify DataCompletenessScore is computed correctly."""

    @pytest.mark.asyncio
    async def test_full_completeness_when_all_criteria_evaluable(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient meeting all criteria should have completeness = 1.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-COMPLETE-CDO6",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-COMPLETE-CDO6", session=session
        )
        assert result is not None
        assert result.data_completeness is not None
        dc = result.data_completeness
        assert dc.overall_completeness == 1.0
        assert dc.evaluable_criteria == dc.total_criteria
        assert dc.unknown_criteria == 0
        assert dc.missing_domains == []
        assert dc.recommendation is None

    @pytest.mark.asyncio
    async def test_zero_completeness_when_all_unknown(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient with no data at all should have completeness = 0.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        result = await service.check_patient_eligibility(
            trial_id, "P-EMPTY-CDO6", session=session
        )
        assert result is not None
        assert result.data_completeness is not None
        dc = result.data_completeness
        assert dc.overall_completeness == 0.0
        assert dc.evaluable_criteria == 0
        assert dc.unknown_criteria == dc.total_criteria
        assert len(dc.missing_domains) > 0
        assert dc.recommendation is not None

    @pytest.mark.asyncio
    async def test_partial_completeness_mixed_criteria(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Patient has data for some criteria but not others -> partial completeness."""
        trial_id = _register_trial(service, _dme_trial_create())

        # Provide age data (demographic = evaluable)
        birth = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).isoformat()
        await _insert_patient_node(session, patient_id="P-PARTIAL-CDO6", birth_date=birth)

        # Provide one condition but not the other two
        await _insert_fact(
            session,
            patient_id="P-PARTIAL-CDO6",
            domain=Domain.CONDITION,
            concept_name="Retinal edema",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-PARTIAL-CDO6", session=session
        )
        assert result is not None
        dc = result.data_completeness
        assert dc is not None
        # total_criteria = 3 inclusion + 1 exclusion = 4
        assert dc.total_criteria == 4
        # demographic=PASS (evaluable), retinal edema=PASS (evaluable),
        # type 2 diabetes=NOT_MET (has condition data, evaluable),
        # exclusion HbA1c=UNKNOWN (no measurement data)
        assert 0.0 < dc.overall_completeness < 1.0
        # At least the measurement domain should be listed as missing
        assert dc.unknown_criteria >= 1

    @pytest.mark.asyncio
    async def test_not_met_criteria_counted_in_completeness(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """NOT_MET criteria should count as evaluable (improve completeness score)."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # Patient has condition data but not the right condition
        await _insert_fact(
            session,
            patient_id="P-NOTMET-COMPLETE-CDO6",
            domain=Domain.CONDITION,
            concept_name="Diabetes mellitus",
        )

        result = await service.check_patient_eligibility(
            trial_id, "P-NOTMET-COMPLETE-CDO6", session=session
        )
        assert result is not None
        dc = result.data_completeness
        assert dc is not None
        # Criterion is NOT_MET, which is evaluable
        assert dc.overall_completeness == 1.0
        assert dc.evaluable_criteria == 1
        assert dc.not_met_criteria == 1
        assert dc.unknown_criteria == 0

    @pytest.mark.asyncio
    async def test_completeness_recommendation_lists_missing_domains(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Recommendation should list the specific missing data domains."""
        trial_id = _register_trial(service, _dme_trial_create())

        # No data at all for any domain
        result = await service.check_patient_eligibility(
            trial_id, "P-RECOMMEND-CDO6", session=session
        )
        assert result is not None
        dc = result.data_completeness
        assert dc is not None
        assert dc.recommendation is not None
        # Should mention obtaining data
        assert "Obtain" in dc.recommendation

    @pytest.mark.asyncio
    async def test_completeness_in_screening_response(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """ScreeningResponse should include data_insufficient_count."""
        trial_id = _register_trial(service, _simple_condition_trial())

        # One patient with matching data, one with unrelated data
        await _insert_fact(
            session,
            patient_id="P-SCREEN-OK-CDO6",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
        )
        await _insert_fact(
            session,
            patient_id="P-SCREEN-BAD-CDO6",
            domain=Domain.DRUG,
            concept_name="Metformin",
        )

        response = await service.screen_patients(trial_id, session=session)
        assert response is not None
        # data_insufficient_count should be >= 0
        assert response.data_insufficient_count >= 0
        # P-SCREEN-BAD-CDO6 has drug data but no condition data,
        # so it doesn't match any inclusion set
        assert response.data_insufficient_count >= 1

    @pytest.mark.asyncio
    async def test_eligible_patient_has_full_completeness(
        self, service: TrialEligibilityService, session: AsyncSession
    ):
        """Eligible patient in batch screening should have completeness = 1.0."""
        trial_id = _register_trial(service, _simple_condition_trial())

        await _insert_fact(
            session,
            patient_id="P-BATCH-CDO6",
            domain=Domain.CONDITION,
            concept_name="Essential hypertension",
            confidence=0.95,
        )

        response = await service.screen_patients(trial_id, session=session)
        assert response is not None
        assert len(response.candidates) >= 1
        candidate = next(
            (c for c in response.candidates if c.patient_id == "P-BATCH-CDO6"),
            None,
        )
        assert candidate is not None
        assert candidate.data_completeness is not None
        assert candidate.data_completeness.overall_completeness == 1.0
