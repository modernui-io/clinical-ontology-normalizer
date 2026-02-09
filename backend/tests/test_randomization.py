"""Tests for Randomization & Blinding Service (CLINICAL-1).

Covers:
- Seed data verification (schemes, assignments, unblinding requests)
- Scheme CRUD (create, read, update, delete with status constraints)
- Scheme lifecycle (validate, activate, lock, complete)
- Validation rules (block sizes, stratification factors, arm count)
- Patient randomization (block, stratified, adaptive, minimization, simple)
- Duplicate patient detection
- Assignment lookup (unblinded vs blinded views)
- Patient assignment lookup
- Unblinding workflow (request, approve, reject, already unblinded)
- Open-label unblinding rejection
- Balance checking (chi-square imbalance, stratified, overall)
- Randomization list generation
- Audit trail
- Metrics computation
- API endpoint integration tests
- Error handling (404s, 400s, invalid transitions)
- Pagination and edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.randomization import (
    AllocationRatio,
    ArmType,
    BlindingLevel,
    RandomizationMethod,
    RandomizationStatus,
    RandomizePatientRequest,
    SchemeCreate,
    SchemeUpdate,
    StratificationFactor,
    TreatmentArm,
    UnblindingApproval,
    UnblindingReason,
    UnblindingRequestCreate,
)
from app.services.randomization_service import (
    RandomizationService,
    get_randomization_service,
    reset_randomization_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

EYLEA_SCHEME = "RAND-EYLEA-001"
DUPIXENT_SCHEME = "RAND-DUP-001"
LIBTAYO_SCHEME = "RAND-LIB-001"

API_PREFIX = "/api/v1/randomization"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_randomization_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RandomizationService:
    """Shorthand for the fresh service."""
    return fresh_service


def _make_arms(n: int = 2) -> list[TreatmentArm]:
    """Create n test arms."""
    arms = []
    types = [ArmType.TREATMENT, ArmType.PLACEBO, ArmType.CONTROL, ArmType.ACTIVE_COMPARATOR]
    for i in range(n):
        arms.append(
            TreatmentArm(
                id=f"ARM-TEST-{i+1}",
                name=f"Test Arm {i+1}",
                arm_type=types[i % len(types)],
                description=f"Test arm {i+1}",
                allocation_weight=1.0,
                current_count=0,
                target_count=50,
            )
        )
    return arms


def _make_strat_factors() -> list[StratificationFactor]:
    """Create test stratification factors."""
    return [
        StratificationFactor(
            id="SF-TEST-1",
            name="Age Group",
            description="Patient age group",
            levels=["<40", "40-65", ">65"],
        ),
    ]


def _make_scheme_create(**kwargs) -> SchemeCreate:
    """Helper to build a SchemeCreate with defaults."""
    defaults = dict(
        trial_id="TRIAL-TEST-001",
        trial_name="Test Trial",
        method=RandomizationMethod.BLOCK,
        blinding_level=BlindingLevel.DOUBLE_BLIND,
        allocation_ratio=AllocationRatio.EQUAL_1_1,
        arms=_make_arms(),
        stratification_factors=[],
        block_sizes=[4, 6],
        seed=42,
    )
    defaults.update(kwargs)
    return SchemeCreate(**defaults)


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_schemes_count(self, svc: RandomizationService):
        """Seed should contain 3 randomization schemes."""
        items, total = svc.list_schemes(limit=100)
        assert total == 3

    def test_seed_scheme_ids(self, svc: RandomizationService):
        """Seed schemes should have expected IDs."""
        for sid in [EYLEA_SCHEME, DUPIXENT_SCHEME, LIBTAYO_SCHEME]:
            scheme = svc.get_scheme(sid)
            assert scheme is not None
            assert scheme.id == sid

    def test_seed_eylea_scheme(self, svc: RandomizationService):
        """EYLEA scheme: 2:1 block, double-blind, 2 arms."""
        scheme = svc.get_scheme(EYLEA_SCHEME)
        assert scheme.method == RandomizationMethod.BLOCK
        assert scheme.blinding_level == BlindingLevel.DOUBLE_BLIND
        assert scheme.allocation_ratio == AllocationRatio.RATIO_2_1
        assert scheme.status == RandomizationStatus.ACTIVE
        assert len(scheme.arms) == 2
        assert scheme.arms[0].arm_type == ArmType.TREATMENT
        assert scheme.arms[1].arm_type == ArmType.SHAM

    def test_seed_dupixent_scheme(self, svc: RandomizationService):
        """Dupixent scheme: 1:1 stratified, double-blind."""
        scheme = svc.get_scheme(DUPIXENT_SCHEME)
        assert scheme.method == RandomizationMethod.STRATIFIED
        assert scheme.allocation_ratio == AllocationRatio.EQUAL_1_1
        assert len(scheme.stratification_factors) == 2

    def test_seed_libtayo_scheme(self, svc: RandomizationService):
        """Libtayo scheme: 3:2 adaptive, double-blind."""
        scheme = svc.get_scheme(LIBTAYO_SCHEME)
        assert scheme.method == RandomizationMethod.ADAPTIVE
        assert scheme.allocation_ratio == AllocationRatio.RATIO_3_2
        assert scheme.arms[0].allocation_weight == 3.0
        assert scheme.arms[1].allocation_weight == 2.0

    def test_seed_assignments_count(self, svc: RandomizationService):
        """Seed should contain 30 assignments (10 per scheme)."""
        items, total = svc.list_assignments(limit=100)
        assert total == 30

    def test_seed_assignments_per_scheme(self, svc: RandomizationService):
        """Each scheme should have 10 assignments."""
        for scheme_id in [EYLEA_SCHEME, DUPIXENT_SCHEME, LIBTAYO_SCHEME]:
            items, total = svc.list_assignments(scheme_id=scheme_id, limit=100)
            assert total == 10, f"Expected 10 for {scheme_id}, got {total}"

    def test_seed_assignment_ids(self, svc: RandomizationService):
        """Seed assignment IDs follow expected pattern."""
        items, _ = svc.list_assignments(scheme_id=EYLEA_SCHEME, limit=10)
        for a in items:
            assert a.id.startswith("ASSIGN-EYLEA-")

    def test_seed_total_randomized(self, svc: RandomizationService):
        """Scheme total_randomized should match assignment count."""
        for sid in [EYLEA_SCHEME, DUPIXENT_SCHEME, LIBTAYO_SCHEME]:
            scheme = svc.get_scheme(sid)
            assert scheme.total_randomized == 10

    def test_seed_unblinding_requests_count(self, svc: RandomizationService):
        """Seed should contain 2 unblinding requests."""
        requests = svc.list_unblinding_requests()
        assert len(requests) == 2

    def test_seed_unblinding_request_pending(self, svc: RandomizationService):
        """One request should be pending."""
        req = svc.get_unblinding_request("UNBLIND-001")
        assert req is not None
        assert req.approved is None
        assert req.urgency == "emergency"

    def test_seed_unblinding_request_approved(self, svc: RandomizationService):
        """One request should be approved."""
        req = svc.get_unblinding_request("UNBLIND-002")
        assert req is not None
        assert req.approved is True
        assert req.approved_by == "Dr. DSMB Chair"

    def test_seed_unblinded_assignment(self, svc: RandomizationService):
        """The approved unblinding should mark the assignment as unblinded."""
        a = svc.get_assignment("ASSIGN-LIB-005")
        assert a is not None
        assert a.is_unblinded is True
        assert a.unblinding_reason == UnblindingReason.SAE_ASSESSMENT

    def test_seed_blinding_codes_unique(self, svc: RandomizationService):
        """All blinding codes should be unique within a scheme."""
        items, _ = svc.list_assignments(scheme_id=EYLEA_SCHEME, limit=100)
        codes = [a.blinding_code for a in items]
        assert len(codes) == len(set(codes))

    def test_seed_audit_trail_not_empty(self, svc: RandomizationService):
        """Audit trail should contain seed entries."""
        entries, total = svc.get_audit_trail(limit=100)
        assert total >= 3  # At least one per scheme creation

    def test_seed_strat_factors_eylea(self, svc: RandomizationService):
        """EYLEA should have 2 stratification factors."""
        scheme = svc.get_scheme(EYLEA_SCHEME)
        assert len(scheme.stratification_factors) == 2
        names = {f.name for f in scheme.stratification_factors}
        assert "Baseline BCVA" in names
        assert "Diabetes Type" in names


# ===========================================================================
# Section 2: Scheme CRUD
# ===========================================================================


class TestSchemeCRUD:
    """Test scheme creation, retrieval, update, and deletion."""

    def test_create_scheme(self, svc: RandomizationService):
        """Create a new scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        assert scheme.id.startswith("RAND-")
        assert scheme.status == RandomizationStatus.DRAFT
        assert scheme.trial_id == "TRIAL-TEST-001"
        assert len(scheme.arms) == 2
        assert scheme.total_randomized == 0

    def test_create_scheme_with_strat(self, svc: RandomizationService):
        """Create scheme with stratification factors."""
        req = _make_scheme_create(
            method=RandomizationMethod.STRATIFIED,
            stratification_factors=_make_strat_factors(),
        )
        scheme = svc.create_scheme(req)
        assert len(scheme.stratification_factors) == 1

    def test_get_scheme_not_found(self, svc: RandomizationService):
        """Nonexistent scheme returns None."""
        assert svc.get_scheme("RAND-NOPE") is None

    def test_update_draft_scheme(self, svc: RandomizationService):
        """Update a DRAFT scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        updated = svc.update_scheme(scheme.id, SchemeUpdate(trial_name="Updated Name"))
        assert updated.trial_name == "Updated Name"

    def test_update_active_scheme_fails(self, svc: RandomizationService):
        """Cannot update an ACTIVE scheme."""
        with pytest.raises(ValueError, match="Cannot update"):
            svc.update_scheme(EYLEA_SCHEME, SchemeUpdate(trial_name="Nope"))

    def test_delete_draft_scheme(self, svc: RandomizationService):
        """Delete a DRAFT scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        assert svc.delete_scheme(scheme.id) is True
        assert svc.get_scheme(scheme.id) is None

    def test_delete_active_scheme_fails(self, svc: RandomizationService):
        """Cannot delete an ACTIVE scheme."""
        with pytest.raises(ValueError, match="DRAFT"):
            svc.delete_scheme(EYLEA_SCHEME)

    def test_delete_nonexistent_scheme(self, svc: RandomizationService):
        """Deleting nonexistent scheme returns False."""
        assert svc.delete_scheme("RAND-NOPE") is False

    def test_list_schemes_filter_by_trial(self, svc: RandomizationService):
        """Filter schemes by trial_id."""
        items, total = svc.list_schemes(trial_id=EYLEA_TRIAL)
        assert total == 1
        assert items[0].trial_id == EYLEA_TRIAL

    def test_list_schemes_filter_by_status(self, svc: RandomizationService):
        """Filter schemes by status."""
        items, total = svc.list_schemes(status=RandomizationStatus.ACTIVE)
        assert total == 3

    def test_list_schemes_filter_by_method(self, svc: RandomizationService):
        """Filter schemes by method."""
        items, total = svc.list_schemes(method=RandomizationMethod.BLOCK)
        assert total == 1
        assert items[0].id == EYLEA_SCHEME

    def test_list_schemes_pagination(self, svc: RandomizationService):
        """Pagination works correctly."""
        items, total = svc.list_schemes(limit=2, offset=0)
        assert total == 3
        assert len(items) == 2
        items2, _ = svc.list_schemes(limit=2, offset=2)
        assert len(items2) == 1


# ===========================================================================
# Section 3: Scheme lifecycle
# ===========================================================================


class TestSchemeLifecycle:
    """Test validate, activate, lock, and complete transitions."""

    def test_validate_draft(self, svc: RandomizationService):
        """DRAFT -> VALIDATED."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        validated = svc.validate_scheme(scheme.id, "Dr. Statistician")
        assert validated.status == RandomizationStatus.VALIDATED
        assert validated.validated_by == "Dr. Statistician"

    def test_validate_requires_two_arms(self, svc: RandomizationService):
        """Validation fails if fewer than 2 arms."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        # Manually remove an arm to simulate invalid state
        scheme.arms = [scheme.arms[0]]
        with pytest.raises(ValueError, match="at least 2 arms"):
            svc.validate_scheme(scheme.id, "validator")

    def test_validate_block_requires_block_sizes(self, svc: RandomizationService):
        """Block randomization requires block_sizes."""
        req = _make_scheme_create(block_sizes=[])
        scheme = svc.create_scheme(req)
        with pytest.raises(ValueError, match="block_sizes"):
            svc.validate_scheme(scheme.id, "validator")

    def test_validate_stratified_requires_factors(self, svc: RandomizationService):
        """Stratified randomization requires stratification_factors."""
        req = _make_scheme_create(
            method=RandomizationMethod.STRATIFIED,
            stratification_factors=[],
        )
        scheme = svc.create_scheme(req)
        with pytest.raises(ValueError, match="stratification_factors"):
            svc.validate_scheme(scheme.id, "validator")

    def test_validate_active_fails(self, svc: RandomizationService):
        """Cannot validate a non-DRAFT scheme."""
        with pytest.raises(ValueError, match="Cannot validate"):
            svc.validate_scheme(EYLEA_SCHEME, "validator")

    def test_activate_validated(self, svc: RandomizationService):
        """VALIDATED -> ACTIVE."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        svc.validate_scheme(scheme.id, "validator")
        activated = svc.activate_scheme(scheme.id)
        assert activated.status == RandomizationStatus.ACTIVE

    def test_activate_draft_fails(self, svc: RandomizationService):
        """Cannot activate a DRAFT scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        with pytest.raises(ValueError, match="Cannot activate"):
            svc.activate_scheme(scheme.id)

    def test_lock_active(self, svc: RandomizationService):
        """ACTIVE -> LOCKED."""
        locked = svc.lock_scheme(EYLEA_SCHEME, "admin")
        assert locked.status == RandomizationStatus.LOCKED
        assert locked.locked_at is not None

    def test_lock_draft_fails(self, svc: RandomizationService):
        """Cannot lock a DRAFT scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        with pytest.raises(ValueError, match="Cannot lock"):
            svc.lock_scheme(scheme.id)

    def test_complete_active(self, svc: RandomizationService):
        """ACTIVE -> COMPLETED."""
        completed = svc.complete_scheme(EYLEA_SCHEME)
        assert completed.status == RandomizationStatus.COMPLETED

    def test_complete_locked(self, svc: RandomizationService):
        """LOCKED -> COMPLETED."""
        svc.lock_scheme(EYLEA_SCHEME)
        completed = svc.complete_scheme(EYLEA_SCHEME)
        assert completed.status == RandomizationStatus.COMPLETED

    def test_complete_draft_fails(self, svc: RandomizationService):
        """Cannot complete a DRAFT scheme."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        with pytest.raises(ValueError, match="Cannot complete"):
            svc.complete_scheme(scheme.id)

    def test_validate_not_found(self, svc: RandomizationService):
        """Validate nonexistent returns None."""
        assert svc.validate_scheme("NOPE", "v") is None

    def test_activate_not_found(self, svc: RandomizationService):
        """Activate nonexistent returns None."""
        assert svc.activate_scheme("NOPE") is None

    def test_lock_not_found(self, svc: RandomizationService):
        """Lock nonexistent returns None."""
        assert svc.lock_scheme("NOPE") is None

    def test_complete_not_found(self, svc: RandomizationService):
        """Complete nonexistent returns None."""
        assert svc.complete_scheme("NOPE") is None


# ===========================================================================
# Section 4: Patient randomization
# ===========================================================================


class TestRandomization:
    """Test the randomization algorithms and constraints."""

    def test_randomize_patient_block(self, svc: RandomizationService):
        """Block randomization produces valid assignment."""
        req = RandomizePatientRequest(patient_id="PAT-NEW-001", randomized_by="coordinator")
        assignment = svc.randomize_patient(EYLEA_SCHEME, req)
        assert assignment.patient_id == "PAT-NEW-001"
        assert assignment.scheme_id == EYLEA_SCHEME
        assert assignment.arm_id in ("ARM-EYLEA-TX", "ARM-EYLEA-SHAM")
        assert assignment.blinding_code.startswith("BL-")
        assert assignment.sequence_number == 11  # After 10 seed entries

    def test_randomize_patient_stratified(self, svc: RandomizationService):
        """Stratified randomization with stratum values."""
        req = RandomizePatientRequest(
            patient_id="PAT-NEW-AD-001",
            randomized_by="coordinator",
            stratum={"Disease Severity": "Severe (IGA 4)", "Prior Systemic Therapy": "Yes"},
        )
        assignment = svc.randomize_patient(DUPIXENT_SCHEME, req)
        assert assignment.stratum is not None
        assert "Disease Severity=Severe (IGA 4)" in assignment.stratum

    def test_randomize_patient_adaptive(self, svc: RandomizationService):
        """Adaptive randomization adjusts weights based on imbalance."""
        req = RandomizePatientRequest(patient_id="PAT-NEW-NSCLC-001", randomized_by="coord")
        assignment = svc.randomize_patient(LIBTAYO_SCHEME, req)
        assert assignment.arm_id in ("ARM-LIB-TX", "ARM-LIB-PBO")

    def test_randomize_duplicate_patient_fails(self, svc: RandomizationService):
        """Cannot randomize the same patient twice in a scheme."""
        with pytest.raises(ValueError, match="already randomized"):
            req = RandomizePatientRequest(patient_id="PAT-DME-001", randomized_by="coord")
            svc.randomize_patient(EYLEA_SCHEME, req)

    def test_randomize_inactive_scheme_fails(self, svc: RandomizationService):
        """Cannot randomize in a non-ACTIVE scheme."""
        req_s = _make_scheme_create()
        scheme = svc.create_scheme(req_s)
        with pytest.raises(ValueError, match="not active"):
            req = RandomizePatientRequest(patient_id="PAT-X", randomized_by="coord")
            svc.randomize_patient(scheme.id, req)

    def test_randomize_nonexistent_scheme(self, svc: RandomizationService):
        """Randomization with unknown scheme raises."""
        with pytest.raises(ValueError, match="not found"):
            req = RandomizePatientRequest(patient_id="PAT-X", randomized_by="coord")
            svc.randomize_patient("RAND-NOPE", req)

    def test_randomize_updates_arm_count(self, svc: RandomizationService):
        """Randomization increments arm current_count."""
        scheme_before = svc.get_scheme(EYLEA_SCHEME)
        total_before = sum(a.current_count for a in scheme_before.arms)

        req = RandomizePatientRequest(patient_id="PAT-NEW-002", randomized_by="coord")
        assignment = svc.randomize_patient(EYLEA_SCHEME, req)

        scheme_after = svc.get_scheme(EYLEA_SCHEME)
        total_after = sum(a.current_count for a in scheme_after.arms)
        assert total_after == total_before + 1

    def test_randomize_updates_total(self, svc: RandomizationService):
        """Randomization increments scheme total_randomized."""
        before = svc.get_scheme(EYLEA_SCHEME).total_randomized
        req = RandomizePatientRequest(patient_id="PAT-NEW-003", randomized_by="coord")
        svc.randomize_patient(EYLEA_SCHEME, req)
        after = svc.get_scheme(EYLEA_SCHEME).total_randomized
        assert after == before + 1

    def test_randomize_creates_audit_entry(self, svc: RandomizationService):
        """Randomization creates an audit entry."""
        req = RandomizePatientRequest(patient_id="PAT-NEW-004", randomized_by="coord")
        svc.randomize_patient(EYLEA_SCHEME, req)
        entries, _ = svc.get_audit_trail(scheme_id=EYLEA_SCHEME, action="PATIENT_RANDOMIZED")
        assert any(e.details.get("patient_id") == "PAT-NEW-004" for e in entries)

    def test_randomize_multiple_sequential(self, svc: RandomizationService):
        """Multiple randomizations produce sequential numbers."""
        for i in range(5):
            req = RandomizePatientRequest(patient_id=f"PAT-SEQ-{i}", randomized_by="coord")
            a = svc.randomize_patient(EYLEA_SCHEME, req)
            assert a.sequence_number == 11 + i

    def test_simple_randomization(self, svc: RandomizationService):
        """Simple randomization works for SIMPLE method schemes."""
        req_s = _make_scheme_create(method=RandomizationMethod.SIMPLE, block_sizes=[])
        scheme = svc.create_scheme(req_s)
        svc.validate_scheme(scheme.id, "v")
        svc.activate_scheme(scheme.id)
        req = RandomizePatientRequest(patient_id="PAT-SIMPLE-1", randomized_by="coord")
        a = svc.randomize_patient(scheme.id, req)
        assert a.arm_id in ("ARM-TEST-1", "ARM-TEST-2")

    def test_minimization_randomization(self, svc: RandomizationService):
        """Minimization method works correctly."""
        req_s = _make_scheme_create(
            method=RandomizationMethod.MINIMIZATION,
            block_sizes=[],
            stratification_factors=_make_strat_factors(),
        )
        scheme = svc.create_scheme(req_s)
        svc.validate_scheme(scheme.id, "v")
        svc.activate_scheme(scheme.id)
        req = RandomizePatientRequest(
            patient_id="PAT-MIN-1",
            randomized_by="coord",
            stratum={"Age Group": "<40"},
        )
        a = svc.randomize_patient(scheme.id, req)
        assert a.arm_id in ("ARM-TEST-1", "ARM-TEST-2")

    def test_locked_scheme_blocks_randomization(self, svc: RandomizationService):
        """Locked scheme cannot accept randomizations."""
        svc.lock_scheme(EYLEA_SCHEME)
        with pytest.raises(ValueError, match="not active"):
            req = RandomizePatientRequest(patient_id="PAT-LOCKED", randomized_by="coord")
            svc.randomize_patient(EYLEA_SCHEME, req)


# ===========================================================================
# Section 5: Assignment lookup
# ===========================================================================


class TestAssignmentLookup:
    """Test unblinded and blinded assignment retrieval."""

    def test_get_assignment(self, svc: RandomizationService):
        """Get a full unblinded assignment."""
        a = svc.get_assignment("ASSIGN-EYLEA-001")
        assert a is not None
        assert a.arm_id in ("ARM-EYLEA-TX", "ARM-EYLEA-SHAM")
        assert a.arm_name in ("EYLEA HD 8mg", "Sham Procedure")

    def test_get_assignment_not_found(self, svc: RandomizationService):
        """Nonexistent assignment returns None."""
        assert svc.get_assignment("ASSIGN-NOPE") is None

    def test_get_blinded_assignment(self, svc: RandomizationService):
        """Blinded view hides arm details."""
        blinded = svc.get_blinded_assignment("ASSIGN-EYLEA-001")
        assert blinded is not None
        assert blinded.blinding_code.startswith("BL-")
        assert not hasattr(blinded, "arm_id") or blinded.model_fields.get("arm_id") is None

    def test_get_blinded_not_found(self, svc: RandomizationService):
        """Nonexistent blinded assignment returns None."""
        assert svc.get_blinded_assignment("ASSIGN-NOPE") is None

    def test_list_assignments_by_scheme(self, svc: RandomizationService):
        """Filter assignments by scheme."""
        items, total = svc.list_assignments(scheme_id=DUPIXENT_SCHEME)
        assert total == 10
        assert all(a.scheme_id == DUPIXENT_SCHEME for a in items)

    def test_list_assignments_by_patient(self, svc: RandomizationService):
        """Filter assignments by patient_id."""
        items, total = svc.list_assignments(patient_id="PAT-DME-001")
        assert total == 1

    def test_list_assignments_by_arm(self, svc: RandomizationService):
        """Filter assignments by arm_id."""
        items, total = svc.list_assignments(arm_id="ARM-EYLEA-TX")
        assert total >= 1
        assert all(a.arm_id == "ARM-EYLEA-TX" for a in items)

    def test_list_assignments_unblinded_filter(self, svc: RandomizationService):
        """Filter assignments by is_unblinded."""
        items, total = svc.list_assignments(is_unblinded=True)
        assert total == 1  # Only ASSIGN-LIB-005

    def test_list_blinded_assignments(self, svc: RandomizationService):
        """List blinded assignments for a scheme."""
        items, total = svc.list_blinded_assignments(scheme_id=EYLEA_SCHEME)
        assert total == 10
        for b in items:
            assert b.blinding_code.startswith("BL-")

    def test_list_assignments_pagination(self, svc: RandomizationService):
        """Pagination on assignment list."""
        items, total = svc.list_assignments(scheme_id=EYLEA_SCHEME, limit=3, offset=0)
        assert total == 10
        assert len(items) == 3

    def test_get_patient_assignment(self, svc: RandomizationService):
        """Look up a patient's assignment in a scheme."""
        a = svc.get_patient_assignment(EYLEA_SCHEME, "PAT-DME-001")
        assert a is not None
        assert a.patient_id == "PAT-DME-001"
        assert a.scheme_id == EYLEA_SCHEME

    def test_get_patient_assignment_not_found(self, svc: RandomizationService):
        """Patient not in scheme returns None."""
        assert svc.get_patient_assignment(EYLEA_SCHEME, "PAT-NOPE") is None

    def test_blinded_assignment_model_no_arm_fields(self, svc: RandomizationService):
        """BlindedAssignment should not contain arm_id or arm_name."""
        blinded = svc.get_blinded_assignment("ASSIGN-EYLEA-001")
        data = blinded.model_dump()
        assert "arm_id" not in data
        assert "arm_name" not in data


# ===========================================================================
# Section 6: Unblinding workflow
# ===========================================================================


class TestUnblinding:
    """Test unblinding request, approval, and rejection workflow."""

    def test_create_unblinding_request(self, svc: RandomizationService):
        """Create a new unblinding request."""
        req = UnblindingRequestCreate(
            assignment_id="ASSIGN-EYLEA-001",
            patient_id="PAT-DME-001",
            requestor="Dr. Emergency",
            reason=UnblindingReason.MEDICAL_EMERGENCY,
            urgency="emergency",
        )
        result = svc.create_unblinding_request(req)
        assert result.id.startswith("UNBLIND-")
        assert result.approved is None
        assert result.reason == UnblindingReason.MEDICAL_EMERGENCY

    def test_create_unblinding_already_unblinded(self, svc: RandomizationService):
        """Cannot request unblinding for already-unblinded assignment."""
        with pytest.raises(ValueError, match="already unblinded"):
            svc.create_unblinding_request(UnblindingRequestCreate(
                assignment_id="ASSIGN-LIB-005",
                patient_id="PAT-NSCLC-005",
                requestor="Dr. X",
                reason=UnblindingReason.MEDICAL_EMERGENCY,
            ))

    def test_create_unblinding_bad_assignment(self, svc: RandomizationService):
        """Cannot create request for nonexistent assignment."""
        with pytest.raises(ValueError, match="not found"):
            svc.create_unblinding_request(UnblindingRequestCreate(
                assignment_id="ASSIGN-NOPE",
                patient_id="PAT-X",
                requestor="Dr. X",
                reason=UnblindingReason.MEDICAL_EMERGENCY,
            ))

    def test_approve_unblinding(self, svc: RandomizationService):
        """Approve a pending unblinding request."""
        approval = UnblindingApproval(approved=True, approved_by="Dr. DSMB")
        result = svc.approve_unblinding("UNBLIND-001", approval)
        assert result.approved is True
        assert result.approved_by == "Dr. DSMB"
        # Check assignment is now unblinded
        a = svc.get_assignment("ASSIGN-EYLEA-003")
        assert a.is_unblinded is True
        assert a.unblinding_reason == UnblindingReason.MEDICAL_EMERGENCY

    def test_reject_unblinding(self, svc: RandomizationService):
        """Reject a pending unblinding request."""
        approval = UnblindingApproval(approved=False, approved_by="Dr. DSMB")
        result = svc.approve_unblinding("UNBLIND-001", approval)
        assert result.approved is False
        # Assignment should remain blinded
        a = svc.get_assignment("ASSIGN-EYLEA-003")
        assert a.is_unblinded is False

    def test_approve_already_decided(self, svc: RandomizationService):
        """Cannot approve/reject already-decided request."""
        with pytest.raises(ValueError, match="already been decided"):
            svc.approve_unblinding(
                "UNBLIND-002", UnblindingApproval(approved=True, approved_by="Dr. X")
            )

    def test_approve_not_found(self, svc: RandomizationService):
        """Approve nonexistent request returns None."""
        result = svc.approve_unblinding(
            "UNBLIND-NOPE", UnblindingApproval(approved=True, approved_by="Dr. X")
        )
        assert result is None

    def test_list_unblinding_requests_pending(self, svc: RandomizationService):
        """Filter for pending requests only."""
        items = svc.list_unblinding_requests(pending_only=True)
        assert len(items) == 1
        assert items[0].approved is None

    def test_list_unblinding_requests_by_scheme(self, svc: RandomizationService):
        """Filter unblinding requests by scheme."""
        items = svc.list_unblinding_requests(scheme_id=LIBTAYO_SCHEME)
        assert len(items) == 1
        assert items[0].id == "UNBLIND-002"

    def test_unblinding_creates_audit_entry(self, svc: RandomizationService):
        """Approving unblinding creates audit entries."""
        svc.approve_unblinding("UNBLIND-001", UnblindingApproval(approved=True, approved_by="Dr. DSMB"))
        entries, _ = svc.get_audit_trail(action="PATIENT_UNBLINDED")
        assert any(e.details.get("patient_id") == "PAT-DME-003" for e in entries)

    def test_rejection_creates_audit_entry(self, svc: RandomizationService):
        """Rejecting unblinding creates audit entry."""
        svc.approve_unblinding("UNBLIND-001", UnblindingApproval(approved=False, approved_by="Dr. X"))
        entries, _ = svc.get_audit_trail(action="UNBLINDING_REJECTED")
        assert len(entries) >= 1

    def test_unblinding_request_creates_audit(self, svc: RandomizationService):
        """Creating an unblinding request creates audit entry."""
        svc.create_unblinding_request(UnblindingRequestCreate(
            assignment_id="ASSIGN-EYLEA-002",
            patient_id="PAT-DME-002",
            requestor="Dr. Emergency",
            reason=UnblindingReason.SAE_ASSESSMENT,
        ))
        entries, _ = svc.get_audit_trail(action="UNBLINDING_REQUESTED")
        assert any(e.details.get("patient_id") == "PAT-DME-002" for e in entries)

    def test_create_unblinding_open_label_fails(self, svc: RandomizationService):
        """Cannot request unblinding for an open-label study."""
        # Create an open-label scheme with assignments
        req_s = _make_scheme_create(
            blinding_level=BlindingLevel.OPEN_LABEL,
            block_sizes=[4],
        )
        scheme = svc.create_scheme(req_s)
        svc.validate_scheme(scheme.id, "v")
        svc.activate_scheme(scheme.id)
        req_r = RandomizePatientRequest(patient_id="PAT-OL-1", randomized_by="coord")
        assignment = svc.randomize_patient(scheme.id, req_r)

        with pytest.raises(ValueError, match="open-label"):
            svc.create_unblinding_request(UnblindingRequestCreate(
                assignment_id=assignment.id,
                patient_id="PAT-OL-1",
                requestor="Dr. X",
                reason=UnblindingReason.MEDICAL_EMERGENCY,
            ))


# ===========================================================================
# Section 7: Balance checking
# ===========================================================================


class TestBalanceChecking:
    """Test randomization balance analysis."""

    def test_balance_report_exists(self, svc: RandomizationService):
        """Balance report is generated for existing scheme."""
        report = svc.check_balance(EYLEA_SCHEME)
        assert report is not None
        assert report.scheme_id == EYLEA_SCHEME
        assert isinstance(report.overall_imbalance, float)

    def test_balance_report_not_found(self, svc: RandomizationService):
        """Balance report for nonexistent scheme returns None."""
        assert svc.check_balance("RAND-NOPE") is None

    def test_balance_has_arm_totals(self, svc: RandomizationService):
        """Balance report includes arm totals."""
        report = svc.check_balance(EYLEA_SCHEME)
        assert "ARM-EYLEA-TX" in report.arm_totals
        assert "ARM-EYLEA-SHAM" in report.arm_totals
        assert sum(report.arm_totals.values()) == 10

    def test_balance_stratified_scheme(self, svc: RandomizationService):
        """Balance check includes stratification factor analysis."""
        report = svc.check_balance(DUPIXENT_SCHEME)
        assert len(report.factors) >= 1

    def test_balance_acceptable_flag(self, svc: RandomizationService):
        """Balance report has acceptable flag."""
        report = svc.check_balance(EYLEA_SCHEME)
        assert isinstance(report.acceptable, bool)

    def test_balance_imbalance_score_non_negative(self, svc: RandomizationService):
        """Imbalance scores should be non-negative."""
        for sid in [EYLEA_SCHEME, DUPIXENT_SCHEME, LIBTAYO_SCHEME]:
            report = svc.check_balance(sid)
            assert report.overall_imbalance >= 0.0

    def test_balance_empty_scheme(self, svc: RandomizationService):
        """Balance check on scheme with no assignments."""
        req = _make_scheme_create()
        scheme = svc.create_scheme(req)
        report = svc.check_balance(scheme.id)
        assert report is not None
        assert report.overall_imbalance == 0.0
        assert report.acceptable is True

    def test_balance_factor_levels(self, svc: RandomizationService):
        """Factor balance check includes levels."""
        report = svc.check_balance(EYLEA_SCHEME)
        for f in report.factors:
            assert isinstance(f.levels, list)
            assert isinstance(f.counts_per_arm, dict)


# ===========================================================================
# Section 8: Randomization list generation
# ===========================================================================


class TestRandomizationList:
    """Test pre-generated randomization list."""

    def test_generate_list(self, svc: RandomizationService):
        """Generate a randomization list."""
        result = svc.generate_randomization_list(EYLEA_SCHEME, count=20)
        assert len(result) == 20
        for entry in result:
            assert "sequence" in entry
            assert "arm_id" in entry
            assert "arm_name" in entry
            assert "blinding_code" in entry

    def test_generate_list_deterministic(self, svc: RandomizationService):
        """Same seed produces same list."""
        list1 = svc.generate_randomization_list(EYLEA_SCHEME, count=10)
        list2 = svc.generate_randomization_list(EYLEA_SCHEME, count=10)
        assert list1 == list2

    def test_generate_list_not_found(self, svc: RandomizationService):
        """Nonexistent scheme raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            svc.generate_randomization_list("RAND-NOPE")

    def test_generate_list_sequences(self, svc: RandomizationService):
        """Sequences are 1-indexed and contiguous."""
        result = svc.generate_randomization_list(EYLEA_SCHEME, count=10)
        for i, entry in enumerate(result):
            assert entry["sequence"] == i + 1


# ===========================================================================
# Section 9: Audit trail
# ===========================================================================


class TestAuditTrail:
    """Test audit trail recording and retrieval."""

    def test_audit_trail_has_entries(self, svc: RandomizationService):
        """Audit trail is populated on init."""
        entries, total = svc.get_audit_trail()
        assert total >= 3

    def test_audit_filter_by_scheme(self, svc: RandomizationService):
        """Filter audit by scheme ID."""
        entries, total = svc.get_audit_trail(scheme_id=EYLEA_SCHEME)
        assert total >= 1
        assert all(e.scheme_id == EYLEA_SCHEME for e in entries)

    def test_audit_filter_by_action(self, svc: RandomizationService):
        """Filter audit by action."""
        entries, total = svc.get_audit_trail(action="SCHEME_CREATED")
        assert total == 3  # One per scheme

    def test_audit_pagination(self, svc: RandomizationService):
        """Audit trail supports pagination."""
        entries1, total = svc.get_audit_trail(limit=2, offset=0)
        assert len(entries1) == 2
        entries2, _ = svc.get_audit_trail(limit=2, offset=2)
        assert len(entries2) >= 1
        # No overlap
        ids1 = {e.id for e in entries1}
        ids2 = {e.id for e in entries2}
        assert ids1.isdisjoint(ids2)

    def test_audit_entry_structure(self, svc: RandomizationService):
        """Audit entries have required fields."""
        entries, _ = svc.get_audit_trail(limit=1)
        e = entries[0]
        assert e.id is not None
        assert e.scheme_id is not None
        assert e.action is not None
        assert e.actor is not None
        assert e.timestamp is not None

    def test_audit_scheme_create_records(self, svc: RandomizationService):
        """Creating a scheme adds to audit trail."""
        before_entries, before_total = svc.get_audit_trail()
        svc.create_scheme(_make_scheme_create())
        after_entries, after_total = svc.get_audit_trail()
        assert after_total == before_total + 1


# ===========================================================================
# Section 10: Metrics
# ===========================================================================


class TestMetrics:
    """Test aggregated metrics computation."""

    def test_metrics_total_schemes(self, svc: RandomizationService):
        """Metrics report total schemes."""
        m = svc.get_metrics()
        assert m.total_schemes == 3

    def test_metrics_active_schemes(self, svc: RandomizationService):
        """Metrics report active schemes."""
        m = svc.get_metrics()
        assert m.active_schemes == 3

    def test_metrics_total_randomized(self, svc: RandomizationService):
        """Metrics report total randomized patients."""
        m = svc.get_metrics()
        assert m.total_randomized == 30

    def test_metrics_unblinded(self, svc: RandomizationService):
        """Metrics report total unblinded."""
        m = svc.get_metrics()
        assert m.total_unblinded == 1

    def test_metrics_pending_requests(self, svc: RandomizationService):
        """Metrics report pending unblinding requests."""
        m = svc.get_metrics()
        assert m.pending_unblinding_requests == 1

    def test_metrics_by_method(self, svc: RandomizationService):
        """Metrics break down by method."""
        m = svc.get_metrics()
        assert m.schemes_by_method["BLOCK"] == 1
        assert m.schemes_by_method["STRATIFIED"] == 1
        assert m.schemes_by_method["ADAPTIVE"] == 1

    def test_metrics_by_blinding(self, svc: RandomizationService):
        """Metrics break down by blinding level."""
        m = svc.get_metrics()
        assert m.schemes_by_blinding["DOUBLE_BLIND"] == 3

    def test_metrics_by_status(self, svc: RandomizationService):
        """Metrics break down by status."""
        m = svc.get_metrics()
        assert m.schemes_by_status["ACTIVE"] == 3

    def test_metrics_randomizations_by_scheme(self, svc: RandomizationService):
        """Metrics report randomizations per scheme."""
        m = svc.get_metrics()
        assert m.randomizations_by_scheme[EYLEA_SCHEME] == 10
        assert m.randomizations_by_scheme[DUPIXENT_SCHEME] == 10
        assert m.randomizations_by_scheme[LIBTAYO_SCHEME] == 10

    def test_metrics_imbalance_score(self, svc: RandomizationService):
        """Metrics report average imbalance."""
        m = svc.get_metrics()
        assert isinstance(m.average_imbalance_score, float)
        assert m.average_imbalance_score >= 0.0


# ===========================================================================
# Section 11: Stats (prewarm)
# ===========================================================================


class TestStats:
    """Test service stats for prewarm."""

    def test_stats_structure(self, svc: RandomizationService):
        """Stats returns expected keys."""
        stats = svc.get_stats()
        assert "total_schemes" in stats
        assert "total_assignments" in stats
        assert "total_unblinding_requests" in stats
        assert "audit_entries" in stats

    def test_stats_values(self, svc: RandomizationService):
        """Stats values match seed data."""
        stats = svc.get_stats()
        assert stats["total_schemes"] == 3
        assert stats["total_assignments"] == 30
        assert stats["total_unblinding_requests"] == 2


# ===========================================================================
# Section 12: API integration tests
# ===========================================================================


@pytest.mark.anyio
class TestAPISchemes:
    """Test scheme API endpoints."""

    async def test_list_schemes(self):
        """GET /schemes returns seed data."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    async def test_list_schemes_filter_method(self):
        """GET /schemes?method=BLOCK filters correctly."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes", params={"method": "BLOCK"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_get_scheme(self):
        """GET /schemes/{id} returns scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}")
        assert resp.status_code == 200
        assert resp.json()["id"] == EYLEA_SCHEME

    async def test_get_scheme_404(self):
        """GET /schemes/{id} returns 404 for unknown."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/RAND-NOPE")
        assert resp.status_code == 404

    async def test_create_scheme(self):
        """POST /schemes creates new scheme."""
        body = {
            "trial_id": "TRIAL-API-001",
            "trial_name": "API Test Trial",
            "method": "BLOCK",
            "blinding_level": "DOUBLE_BLIND",
            "allocation_ratio": "EQUAL_1_1",
            "arms": [
                {"id": "ARM-A", "name": "Arm A", "arm_type": "TREATMENT", "allocation_weight": 1.0, "current_count": 0, "target_count": 50},
                {"id": "ARM-B", "name": "Arm B", "arm_type": "PLACEBO", "allocation_weight": 1.0, "current_count": 0, "target_count": 50},
            ],
            "block_sizes": [4, 6],
            "seed": 42,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "DRAFT"

    async def test_update_scheme_active_400(self):
        """PUT /schemes/{id} returns 400 for active scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"{API_PREFIX}/schemes/{EYLEA_SCHEME}",
                json={"trial_name": "Nope"},
            )
        assert resp.status_code == 400

    async def test_delete_scheme_active_400(self):
        """DELETE /schemes/{id} returns 400 for active scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}")
        assert resp.status_code == 400

    async def test_delete_scheme_404(self):
        """DELETE /schemes/{id} returns 404 for unknown."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"{API_PREFIX}/schemes/RAND-NOPE")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPILifecycle:
    """Test scheme lifecycle API endpoints."""

    async def test_validate_activate(self):
        """POST validate then activate a scheme."""
        body = {
            "trial_id": "TRIAL-LC",
            "trial_name": "Lifecycle Test",
            "method": "BLOCK",
            "blinding_level": "SINGLE_BLIND",
            "allocation_ratio": "EQUAL_1_1",
            "arms": [
                {"id": "ARM-1", "name": "Arm 1", "arm_type": "TREATMENT", "allocation_weight": 1.0, "current_count": 0, "target_count": 50},
                {"id": "ARM-2", "name": "Arm 2", "arm_type": "CONTROL", "allocation_weight": 1.0, "current_count": 0, "target_count": 50},
            ],
            "block_sizes": [4],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(f"{API_PREFIX}/schemes", json=body)
            scheme_id = create_resp.json()["id"]

            val_resp = await client.post(f"{API_PREFIX}/schemes/{scheme_id}/validate")
            assert val_resp.status_code == 200
            assert val_resp.json()["status"] == "VALIDATED"

            act_resp = await client.post(f"{API_PREFIX}/schemes/{scheme_id}/activate")
            assert act_resp.status_code == 200
            assert act_resp.json()["status"] == "ACTIVE"

    async def test_lock_scheme(self):
        """POST /schemes/{id}/lock locks active scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/lock")
        assert resp.status_code == 200
        assert resp.json()["status"] == "LOCKED"

    async def test_complete_scheme(self):
        """POST /schemes/{id}/complete completes scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    async def test_validate_active_400(self):
        """Cannot validate an active scheme."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/validate")
        assert resp.status_code == 400


@pytest.mark.anyio
class TestAPIRandomize:
    """Test randomization API endpoint."""

    async def test_randomize_patient(self):
        """POST /schemes/{id}/randomize creates assignment."""
        body = {"patient_id": "PAT-API-001", "randomized_by": "api-user"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/randomize", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-API-001"
        assert data["scheme_id"] == EYLEA_SCHEME

    async def test_randomize_duplicate_400(self):
        """Cannot randomize same patient twice."""
        body = {"patient_id": "PAT-DME-001", "randomized_by": "api-user"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/randomize", json=body)
        assert resp.status_code == 400

    async def test_randomize_nonexistent_scheme_400(self):
        """Randomize with unknown scheme returns 400."""
        body = {"patient_id": "PAT-X", "randomized_by": "api-user"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/schemes/RAND-NOPE/randomize", json=body)
        assert resp.status_code == 400


@pytest.mark.anyio
class TestAPIAssignments:
    """Test assignment API endpoints."""

    async def test_list_assignments(self):
        """GET /assignments returns all."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 30

    async def test_list_blinded_assignments(self):
        """GET /assignments/blinded returns blinded views."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/blinded", params={"scheme_id": EYLEA_SCHEME})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        for item in data["items"]:
            assert "arm_id" not in item
            assert "arm_name" not in item

    async def test_get_assignment(self):
        """GET /assignments/{id} returns unblinded."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-EYLEA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "arm_id" in data
        assert "arm_name" in data

    async def test_get_assignment_404(self):
        """GET /assignments/{id} returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-NOPE")
        assert resp.status_code == 404

    async def test_get_blinded_assignment(self):
        """GET /assignments/{id}/blinded returns blinded."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/ASSIGN-EYLEA-001/blinded")
        assert resp.status_code == 200
        data = resp.json()
        assert "arm_id" not in data

    async def test_get_patient_assignment(self):
        """GET /assignments/patient/{scheme_id}/{patient_id} returns assignment."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/patient/{EYLEA_SCHEME}/PAT-DME-001")
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == "PAT-DME-001"

    async def test_get_patient_assignment_404(self):
        """GET /assignments/patient returns 404 for unknown."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/assignments/patient/{EYLEA_SCHEME}/PAT-NOPE")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPIBalance:
    """Test balance and list API endpoints."""

    async def test_balance_check(self):
        """GET /schemes/{id}/balance returns report."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_imbalance" in data
        assert "arm_totals" in data

    async def test_balance_404(self):
        """GET /schemes/{id}/balance returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/RAND-NOPE/balance")
        assert resp.status_code == 404

    async def test_generate_list(self):
        """GET /schemes/{id}/list returns pre-generated list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/{EYLEA_SCHEME}/list", params={"count": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10

    async def test_generate_list_404(self):
        """GET /schemes/{id}/list returns 404 for unknown."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/RAND-NOPE/list")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPIUnblinding:
    """Test unblinding API endpoints."""

    async def test_create_unblinding_request(self):
        """POST /unblinding/request creates request."""
        body = {
            "assignment_id": "ASSIGN-EYLEA-001",
            "patient_id": "PAT-DME-001",
            "requestor": "Dr. API",
            "reason": "MEDICAL_EMERGENCY",
            "urgency": "emergency",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/unblinding/request", json=body)
        assert resp.status_code == 201
        assert resp.json()["approved"] is None

    async def test_create_unblinding_bad_assignment(self):
        """POST /unblinding/request returns 400 for bad assignment."""
        body = {
            "assignment_id": "ASSIGN-NOPE",
            "patient_id": "PAT-X",
            "requestor": "Dr. API",
            "reason": "MEDICAL_EMERGENCY",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/unblinding/request", json=body)
        assert resp.status_code == 400

    async def test_list_unblinding_requests(self):
        """GET /unblinding/requests lists all."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/unblinding/requests")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_get_unblinding_request(self):
        """GET /unblinding/requests/{id} returns request."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/unblinding/requests/UNBLIND-001")
        assert resp.status_code == 200

    async def test_get_unblinding_request_404(self):
        """GET /unblinding/requests/{id} returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/unblinding/requests/UNBLIND-NOPE")
        assert resp.status_code == 404

    async def test_approve_unblinding(self):
        """POST /unblinding/requests/{id}/approve approves."""
        body = {"approved": True, "approved_by": "Dr. DSMB API"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/unblinding/requests/UNBLIND-001/approve", json=body)
        assert resp.status_code == 200
        assert resp.json()["approved"] is True

    async def test_approve_already_decided_400(self):
        """POST approve on decided request returns 400."""
        body = {"approved": True, "approved_by": "Dr. X"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"{API_PREFIX}/unblinding/requests/UNBLIND-002/approve", json=body)
        assert resp.status_code == 400


@pytest.mark.anyio
class TestAPIAuditAndMetrics:
    """Test audit trail and metrics API endpoints."""

    async def test_audit_trail(self):
        """GET /audit returns entries."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/audit")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    async def test_audit_filter_action(self):
        """GET /audit?action=SCHEME_CREATED filters."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/audit", params={"action": "SCHEME_CREATED"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    async def test_metrics(self):
        """GET /schemes/metrics returns metrics."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{API_PREFIX}/schemes/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_schemes"] == 3
        assert data["total_randomized"] == 30
