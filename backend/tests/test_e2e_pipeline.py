"""End-to-end pipeline tests: FHIR Bundle import -> ClinicalFact creation -> Trial screening.

QA-3.5: End-to-End Pipeline Tests

These integration tests exercise the full data flow from FHIR Bundle ingestion
through ClinicalFact/KGNode creation to trial eligibility screening. They verify
that:

1. FHIR Bundles are correctly parsed and imported
2. ClinicalFacts are created with correct domain, concept_name, and values
3. KGNodes (including Patient nodes with demographics) are created
4. Trial eligibility screening queries the imported data correctly
5. Eligible, excluded, and incomplete-data patients are handled properly

Test scenarios:
- DME Patient Flow: Patient with DME + diabetes + HbA1c -> eligible for EYLEA trial
- Exclusion Patient Flow: Patient with DME + diabetes + high HbA1c -> excluded
- Incomplete Data Flow: Patient with only diabetes (no DME) -> ineligible
- AD Patient Flow: Patient with atopic dermatitis -> eligible for Dupixent trial
- AD Exclusion Flow: Patient with AD + cancer -> excluded from Dupixent trial

Uses the same async SQLite in-memory database pattern from test_trial_eligibility.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.clinical_fact import ClinicalFact
from app.models.data_lineage import DataLineageRecord
from app.models.knowledge_graph import KGEdge, KGNode
from app.schemas.base import Assertion, Domain
from app.schemas.knowledge_graph import NodeType
from app.schemas.trial import TrialCreate
from app.models.trial import TrialPhase, TrialStatus
from app.services.fhir_import import FHIRImportService
from app.services.trial_eligibility_service import TrialEligibilityService


# =============================================================================
# Async Engine / Session Fixtures
# =============================================================================


def _create_tables_ignoring_index_errors(sync_conn, tables):
    """Create tables, catching duplicate index errors from SQLite.

    KGEdge has both `index=True` on columns and explicit Index entries
    in __table_args__ that can produce duplicate index name errors in
    SQLite. We create tables individually and ignore those errors.
    """
    import sqlite3

    for table in tables:
        try:
            table.create(sync_conn, checkfirst=True)
        except Exception as exc:
            # SQLite raises OperationalError for duplicate index names.
            # PostgreSQL handles this gracefully, but SQLite does not.
            if "already exists" in str(exc):
                pass
            else:
                raise


@pytest.fixture(scope="function")
async def engine():
    """Create an async SQLite in-memory engine for e2e testing.

    Creates the tables needed for both FHIR import and eligibility screening:
    ClinicalFact, KGNode, KGEdge.
    """
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    tables = [
        ClinicalFact.__table__,
        KGNode.__table__,
        KGEdge.__table__,
        DataLineageRecord.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(_create_tables_ignoring_index_errors, tables)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=tables)
    await eng.dispose()


@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create an async database session for e2e testing."""
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=True,
    )
    async with factory() as sess:
        yield sess


@pytest.fixture
def fhir_service() -> FHIRImportService:
    """Create a FHIRImportService (no FHIR server needed for bundle import)."""
    return FHIRImportService(fhir_base_url="http://not-used")


@pytest.fixture
def trial_service() -> TrialEligibilityService:
    """Create a fresh TrialEligibilityService.

    Marks _loaded_from_db=True so it does not attempt to query
    the Trial table (which does not exist in these e2e tests).
    """
    svc = TrialEligibilityService()
    svc._loaded_from_db = True
    return svc


# =============================================================================
# FHIR Bundle Builders
# =============================================================================


def _build_fhir_bundle(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap FHIR resource entries into a Bundle."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in entries],
    }


def _patient_resource(
    patient_id: str,
    given: str,
    family: str,
    birth_date: str,
    gender: str = "male",
) -> dict[str, Any]:
    """Build a minimal FHIR R4 Patient resource."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"given": [given], "family": family}],
        "gender": gender,
        "birthDate": birth_date,
    }


def _condition_resource(
    condition_id: str,
    code: str,
    display: str,
    system: str = "http://hl7.org/fhir/sid/icd-10-cm",
    status: str = "active",
) -> dict[str, Any]:
    """Build a minimal FHIR R4 Condition resource."""
    return {
        "resourceType": "Condition",
        "id": condition_id,
        "code": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": status,
                }
            ]
        },
    }


def _observation_resource(
    observation_id: str,
    code: str,
    display: str,
    value: float,
    unit: str,
    system: str = "http://loinc.org",
    category_code: str = "laboratory",
) -> dict[str, Any]:
    """Build a minimal FHIR R4 Observation resource (lab result)."""
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": category_code,
                    }
                ]
            }
        ],
        "code": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
        "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org"},
    }


def _medication_resource(
    med_id: str,
    code: str,
    display: str,
    system: str = "http://www.nlm.nih.gov/research/umls/rxnorm",
    status: str = "active",
) -> dict[str, Any]:
    """Build a minimal FHIR R4 MedicationRequest resource."""
    return {
        "resourceType": "MedicationRequest",
        "id": med_id,
        "status": status,
        "medicationCodeableConcept": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
    }


# =============================================================================
# Trial Definitions
# =============================================================================


def _dme_trial() -> TrialCreate:
    """EYLEA HD - Diabetic Macular Edema trial.

    Inclusion: age >= 18, DME condition, Type 2 Diabetes condition
    Exclusion: HbA1c >= 12%
    """
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
    )


def _ad_trial() -> TrialCreate:
    """DUPIXENT - Atopic Dermatitis trial.

    Inclusion: age 18-75, Atopic Dermatitis condition
    Exclusion: Active cancer
    """
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
            ],
            "root_operator": "AND",
        },
        enrollment_target=600,
        site_count=250,
    )


def _register_trial(service: TrialEligibilityService, create: TrialCreate) -> str:
    """Register a trial and return its ID."""
    response = service.create_trial(create)
    return str(response.id)


# =============================================================================
# Test 1: DME Patient Flow (Eligible)
# =============================================================================


class TestDMEPatientEligibleFlow:
    """End-to-end: FHIR Bundle with DME patient -> import -> screen -> ELIGIBLE.

    Patient has:
    - Type 2 DM with diabetic retinopathy with macular edema (E11.311)
    - Type 2 diabetes mellitus (E11)
    - HbA1c = 7.5% (below 12% exclusion threshold)
    - Age 55 (adult, meets demographic criterion)
    - Metformin medication

    Expected: Patient is eligible for EYLEA HD DME trial.
    """

    @pytest.mark.asyncio
    async def test_dme_eligible_patient_full_pipeline(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Full pipeline: FHIR import -> verify facts -> screen -> eligible."""
        patient_id = "e2e-dme-eligible-001"

        # Birth date ~55 years ago
        birth_date = (datetime.now(timezone.utc) - timedelta(days=55 * 365)).strftime("%Y-%m-%d")

        # Step 1: Build a FHIR Bundle
        bundle = _build_fhir_bundle([
            _patient_resource("fhir-dme-001", "Robert", "Chen", birth_date),
            _condition_resource(
                "cond-dme-001", "E11.311",
                "Type 2 DM with diabetic retinopathy with macular edema",
            ),
            _condition_resource(
                "cond-dm-001", "E11",
                "Type 2 diabetes mellitus",
            ),
            _observation_resource(
                "obs-hba1c-001", "4548-4",
                "Hemoglobin A1c", 7.5, "%",
            ),
            _medication_resource(
                "med-met-001", "860975",
                "Metformin 500 MG",
            ),
        ])

        # Step 2: Import via FHIRImportService
        result = await fhir_service.import_bundle(session, bundle, patient_id)

        assert result["success"] is True
        assert result["patient_id"] == patient_id
        assert result["conditions"] >= 2, f"Expected >= 2 conditions, got {result['conditions']}"
        assert result["observations"] >= 1, f"Expected >= 1 observation, got {result['observations']}"
        assert result["medications"] >= 1, f"Expected >= 1 medication, got {result['medications']}"

        # Step 3: Verify ClinicalFacts were created
        facts_result = await session.execute(
            select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        )
        facts = facts_result.scalars().all()
        assert len(facts) >= 4, f"Expected >= 4 facts, got {len(facts)}"

        # Verify specific clinical facts exist
        condition_facts = [f for f in facts if f.domain == Domain.CONDITION]
        assert len(condition_facts) >= 2

        dme_facts = [
            f for f in condition_facts
            if "macular edema" in f.concept_name.lower()
            or "retinopathy" in f.concept_name.lower()
        ]
        assert len(dme_facts) >= 1, "Expected at least one DME-related condition fact"

        diabetes_facts = [
            f for f in condition_facts
            if "diabetes" in f.concept_name.lower()
        ]
        assert len(diabetes_facts) >= 1, "Expected at least one diabetes condition fact"

        measurement_facts = [f for f in facts if f.domain == Domain.MEASUREMENT]
        assert len(measurement_facts) >= 1
        hba1c_fact = next(
            (f for f in measurement_facts if "a1c" in f.concept_name.lower()),
            None,
        )
        assert hba1c_fact is not None, "Expected HbA1c measurement fact"
        assert hba1c_fact.value == "7.5"
        assert hba1c_fact.unit == "%"

        drug_facts = [f for f in facts if f.domain == Domain.DRUG]
        assert len(drug_facts) >= 1

        # Step 4: Verify KG nodes were created
        nodes_result = await session.execute(
            select(KGNode).where(KGNode.patient_id == patient_id)
        )
        nodes = nodes_result.scalars().all()
        assert len(nodes) >= 5, f"Expected >= 5 KG nodes, got {len(nodes)}"

        # Verify patient node exists with demographics
        patient_nodes = [n for n in nodes if n.node_type == NodeType.PATIENT]
        assert len(patient_nodes) == 1
        patient_node = patient_nodes[0]
        assert patient_node.properties.get("birth_date") == birth_date
        assert patient_node.properties.get("gender") == "male"

        # Step 5: Register trial and screen the patient
        trial_id = _register_trial(trial_service, _dme_trial())
        eligibility = await trial_service.check_patient_eligibility(
            trial_id, patient_id, session=session,
        )

        assert eligibility is not None
        assert eligibility.eligible is True, (
            f"Expected eligible=True but got False. "
            f"Inclusion met: {eligibility.inclusion_met}, "
            f"Missing: {eligibility.missing_data}, "
            f"Exclusions: {eligibility.exclusion_triggered}"
        )
        assert eligibility.match_score > 0.0
        assert "Adult patients" in eligibility.inclusion_met
        assert "Diabetic Macular Edema" in eligibility.inclusion_met
        assert "Type 2 Diabetes" in eligibility.inclusion_met
        assert len(eligibility.exclusion_triggered) == 0
        assert eligibility.requires_clinician_review is True


# =============================================================================
# Test 2: DME Patient Exclusion Flow (HbA1c too high)
# =============================================================================


class TestDMEPatientExclusionFlow:
    """End-to-end: FHIR Bundle with high HbA1c patient -> import -> screen -> EXCLUDED.

    Patient has:
    - DME condition (E11.311)
    - Type 2 diabetes mellitus (E11)
    - HbA1c = 14.5% (ABOVE 12% exclusion threshold)
    - Age 60 (adult)

    Expected: Patient meets all inclusion but is EXCLUDED due to HbA1c >= 12%.
    """

    @pytest.mark.asyncio
    async def test_dme_excluded_patient_high_hba1c(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Full pipeline: FHIR import -> screen -> excluded by HbA1c."""
        patient_id = "e2e-dme-excluded-001"
        birth_date = (datetime.now(timezone.utc) - timedelta(days=60 * 365)).strftime("%Y-%m-%d")

        # Step 1: Build FHIR Bundle with high HbA1c
        bundle = _build_fhir_bundle([
            _patient_resource("fhir-dme-exc-001", "James", "Williams", birth_date),
            _condition_resource(
                "cond-dme-exc-001", "E11.311",
                "Type 2 DM with diabetic retinopathy with macular edema",
            ),
            _condition_resource(
                "cond-dm-exc-001", "E11",
                "Type 2 diabetes mellitus",
            ),
            _observation_resource(
                "obs-hba1c-exc-001", "4548-4",
                "Hemoglobin A1c", 14.5, "%",
            ),
        ])

        # Step 2: Import
        result = await fhir_service.import_bundle(session, bundle, patient_id)
        assert result["success"] is True
        assert result["conditions"] >= 2
        assert result["observations"] >= 1

        # Step 3: Verify the HbA1c fact was imported with correct value
        hba1c_result = await session.execute(
            select(ClinicalFact).where(
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.domain == Domain.MEASUREMENT,
            )
        )
        hba1c_facts = hba1c_result.scalars().all()
        assert len(hba1c_facts) >= 1
        assert any(f.value == "14.5" for f in hba1c_facts), "HbA1c value should be 14.5"

        # Step 4: Screen against DME trial
        trial_id = _register_trial(trial_service, _dme_trial())
        eligibility = await trial_service.check_patient_eligibility(
            trial_id, patient_id, session=session,
        )

        assert eligibility is not None
        assert eligibility.eligible is False
        assert eligibility.match_score == 0.0, "Score should be 0 when exclusion triggers"
        assert "Uncontrolled diabetes (HbA1c > 12%)" in eligibility.exclusion_triggered
        # Inclusion criteria should still be met
        assert "Diabetic Macular Edema" in eligibility.inclusion_met
        assert "Type 2 Diabetes" in eligibility.inclusion_met


# =============================================================================
# Test 3: Incomplete Data Flow (missing DME condition)
# =============================================================================


class TestIncompleteDataFlow:
    """End-to-end: FHIR Bundle with only diabetes (no DME labs) -> INELIGIBLE with UNKNOWN.

    Patient has:
    - Type 2 diabetes mellitus (E11)
    - Age 50 (adult)
    - No DME condition
    - No HbA1c lab

    Expected: Patient meets age + diabetes criteria but MISSING DME criterion.
    The exclusion criterion (HbA1c) should be UNKNOWN (no measurement data).
    """

    @pytest.mark.asyncio
    async def test_incomplete_data_missing_dme(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Full pipeline: FHIR import -> screen -> ineligible due to missing DME."""
        patient_id = "e2e-incomplete-001"
        birth_date = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).strftime("%Y-%m-%d")

        # Step 1: Build a minimal FHIR Bundle -- only diabetes, no DME or labs
        bundle = _build_fhir_bundle([
            _patient_resource("fhir-inc-001", "Alice", "Johnson", birth_date, gender="female"),
            _condition_resource(
                "cond-dm-inc-001", "E11",
                "Type 2 diabetes mellitus",
            ),
        ])

        # Step 2: Import
        result = await fhir_service.import_bundle(session, bundle, patient_id)
        assert result["success"] is True
        assert result["conditions"] >= 1

        # Step 3: Verify only diabetes fact was created (no DME)
        facts_result = await session.execute(
            select(ClinicalFact).where(ClinicalFact.patient_id == patient_id)
        )
        facts = facts_result.scalars().all()
        condition_facts = [f for f in facts if f.domain == Domain.CONDITION]
        assert len(condition_facts) >= 1
        # Should NOT have any measurement facts
        measurement_facts = [f for f in facts if f.domain == Domain.MEASUREMENT]
        assert len(measurement_facts) == 0, "Should have no measurement facts"

        # Step 4: Screen against DME trial
        trial_id = _register_trial(trial_service, _dme_trial())
        eligibility = await trial_service.check_patient_eligibility(
            trial_id, patient_id, session=session,
        )

        assert eligibility is not None
        assert eligibility.eligible is False, "Should be ineligible -- missing DME condition"

        # The DME criterion should be in missing_data
        assert "Diabetic Macular Edema" in eligibility.missing_data

        # The HbA1c exclusion criterion should report UNKNOWN status
        # (no measurement data at all for this patient)
        hba1c_criterion = next(
            (cr for cr in eligibility.criteria_details
             if cr.criterion_name == "Uncontrolled diabetes (HbA1c > 12%)"),
            None,
        )
        assert hba1c_criterion is not None, "Expected HbA1c exclusion criterion in details"
        assert hba1c_criterion.status == "UNKNOWN", (
            f"Expected UNKNOWN for HbA1c criterion (no lab data), got {hba1c_criterion.status}"
        )

        # Data completeness should reflect missing domains
        assert eligibility.data_completeness is not None
        assert eligibility.data_completeness.overall_completeness < 1.0
        assert eligibility.data_completeness.unknown_criteria >= 1


# =============================================================================
# Test 4: AD Patient Flow (Eligible)
# =============================================================================


class TestADPatientEligibleFlow:
    """End-to-end: FHIR Bundle with AD patient -> import -> screen -> ELIGIBLE.

    Patient has:
    - Atopic dermatitis (L20.9)
    - Age 34 (within 18-75 range)
    - No cancer

    Expected: Patient is eligible for DUPIXENT AD trial.
    """

    @pytest.mark.asyncio
    async def test_ad_eligible_patient_full_pipeline(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Full pipeline: FHIR import -> verify facts -> screen -> eligible."""
        patient_id = "e2e-ad-eligible-001"
        birth_date = (datetime.now(timezone.utc) - timedelta(days=34 * 365)).strftime("%Y-%m-%d")

        # Step 1: Build FHIR Bundle
        bundle = _build_fhir_bundle([
            _patient_resource("fhir-ad-001", "Sarah", "Kim", birth_date, gender="female"),
            _condition_resource(
                "cond-ad-001", "L20.9",
                "Atopic dermatitis, unspecified",
            ),
            _medication_resource(
                "med-tac-001", "372048",
                "Tacrolimus topical",
            ),
        ])

        # Step 2: Import
        result = await fhir_service.import_bundle(session, bundle, patient_id)
        assert result["success"] is True
        assert result["conditions"] >= 1
        assert result["medications"] >= 1

        # Step 3: Verify AD condition fact
        facts_result = await session.execute(
            select(ClinicalFact).where(
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.domain == Domain.CONDITION,
            )
        )
        condition_facts = facts_result.scalars().all()
        ad_facts = [f for f in condition_facts if "atopic dermatitis" in f.concept_name.lower()]
        assert len(ad_facts) >= 1, "Expected atopic dermatitis condition fact"

        # Step 4: Verify patient KG node with demographics
        patient_result = await session.execute(
            select(KGNode).where(
                KGNode.patient_id == patient_id,
                KGNode.node_type == NodeType.PATIENT,
            )
        )
        patient_node = patient_result.scalar_one_or_none()
        assert patient_node is not None
        assert patient_node.properties.get("birth_date") == birth_date

        # Step 5: Screen against AD trial
        trial_id = _register_trial(trial_service, _ad_trial())
        eligibility = await trial_service.check_patient_eligibility(
            trial_id, patient_id, session=session,
        )

        assert eligibility is not None
        assert eligibility.eligible is True, (
            f"Expected eligible=True. "
            f"Met: {eligibility.inclusion_met}, "
            f"Missing: {eligibility.missing_data}, "
            f"Excluded: {eligibility.exclusion_triggered}"
        )
        assert "Adult patients" in eligibility.inclusion_met
        assert "Atopic Dermatitis" in eligibility.inclusion_met
        assert len(eligibility.exclusion_triggered) == 0


# =============================================================================
# Test 5: AD Patient Exclusion Flow (has cancer)
# =============================================================================


class TestADPatientExclusionFlow:
    """End-to-end: FHIR Bundle with AD + cancer -> import -> screen -> EXCLUDED.

    Patient has:
    - Atopic dermatitis (L20.9) -- meets inclusion
    - Malignant neoplasm (C80.1) -- triggers exclusion
    - Age 45 (within range)

    Expected: Patient meets all inclusion but EXCLUDED due to cancer.
    """

    @pytest.mark.asyncio
    async def test_ad_excluded_patient_cancer(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Full pipeline: FHIR import -> screen -> excluded by cancer."""
        patient_id = "e2e-ad-excluded-001"
        birth_date = (datetime.now(timezone.utc) - timedelta(days=45 * 365)).strftime("%Y-%m-%d")

        # Step 1: Build FHIR Bundle with AD + cancer
        bundle = _build_fhir_bundle([
            _patient_resource("fhir-ad-exc-001", "John", "Doe", birth_date),
            _condition_resource(
                "cond-ad-exc-001", "L20.9",
                "Atopic dermatitis, unspecified",
            ),
            _condition_resource(
                "cond-cancer-001", "C80.1",
                "Malignant neoplasm, unspecified",
            ),
        ])

        # Step 2: Import
        result = await fhir_service.import_bundle(session, bundle, patient_id)
        assert result["success"] is True
        assert result["conditions"] >= 2

        # Step 3: Verify both conditions were imported
        facts_result = await session.execute(
            select(ClinicalFact).where(
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.domain == Domain.CONDITION,
            )
        )
        condition_facts = facts_result.scalars().all()
        concept_names_lower = [f.concept_name.lower() for f in condition_facts]
        assert any("atopic dermatitis" in n for n in concept_names_lower)
        assert any("malignant" in n or "neoplasm" in n for n in concept_names_lower)

        # Step 4: Screen against AD trial
        trial_id = _register_trial(trial_service, _ad_trial())
        eligibility = await trial_service.check_patient_eligibility(
            trial_id, patient_id, session=session,
        )

        assert eligibility is not None
        assert eligibility.eligible is False
        assert eligibility.match_score == 0.0, "Score should be 0 when exclusion triggers"
        assert "Active cancer" in eligibility.exclusion_triggered

        # Inclusion criteria should still be met
        assert "Atopic Dermatitis" in eligibility.inclusion_met
        assert "Adult patients" in eligibility.inclusion_met

        # Verify the exclusion criterion detail
        cancer_criterion = next(
            (cr for cr in eligibility.criteria_details if cr.criterion_name == "Active cancer"),
            None,
        )
        assert cancer_criterion is not None
        assert cancer_criterion.status == "FAIL"
        assert len(cancer_criterion.evidence_fact_ids) >= 1


# =============================================================================
# Test 6: Batch Screening After FHIR Import
# =============================================================================


class TestBatchScreeningAfterImport:
    """Import multiple patients via FHIR and batch-screen them.

    Imports two patients:
    1. Eligible DME patient (has all criteria, low HbA1c)
    2. Ineligible patient (has diabetes but no DME)

    Then runs screen_patients and verifies correct counts.
    """

    @pytest.mark.asyncio
    async def test_batch_screening_mixed_patients(
        self,
        fhir_service: FHIRImportService,
        trial_service: TrialEligibilityService,
        session: AsyncSession,
    ):
        """Import two patients and batch-screen for DME trial."""
        birth_date_55 = (datetime.now(timezone.utc) - timedelta(days=55 * 365)).strftime("%Y-%m-%d")
        birth_date_50 = (datetime.now(timezone.utc) - timedelta(days=50 * 365)).strftime("%Y-%m-%d")

        # Patient 1: Eligible -- has DME + diabetes + low HbA1c
        patient_1_id = "e2e-batch-eligible"
        bundle_1 = _build_fhir_bundle([
            _patient_resource("fhir-batch-001", "Patient", "One", birth_date_55),
            _condition_resource("cond-b-dme", "E11.311",
                "Type 2 DM with diabetic retinopathy with macular edema"),
            _condition_resource("cond-b-dm", "E11", "Type 2 diabetes mellitus"),
            _observation_resource("obs-b-hba1c", "4548-4", "Hemoglobin A1c", 7.0, "%"),
        ])
        result_1 = await fhir_service.import_bundle(session, bundle_1, patient_1_id)
        assert result_1["success"] is True

        # Patient 2: Ineligible -- has diabetes only, no DME
        patient_2_id = "e2e-batch-ineligible"
        bundle_2 = _build_fhir_bundle([
            _patient_resource("fhir-batch-002", "Patient", "Two", birth_date_50),
            _condition_resource("cond-b-dm2", "E11", "Type 2 diabetes mellitus"),
        ])
        result_2 = await fhir_service.import_bundle(session, bundle_2, patient_2_id)
        assert result_2["success"] is True

        # Register trial and batch screen
        trial_id = _register_trial(trial_service, _dme_trial())
        response = await trial_service.screen_patients(trial_id, session=session)

        assert response is not None
        assert response.total_patients_screened == 2
        assert response.eligible_count == 1
        assert response.ineligible_count == 1

        # The eligible candidate should be patient_1
        assert len(response.candidates) >= 1
        eligible_ids = [c.patient_id for c in response.candidates if c.eligible]
        assert patient_1_id in eligible_ids
