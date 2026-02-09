"""Tests for Contract Lifecycle Management (CLO-6).

Covers:
- Seed data verification (10 contracts, 6 IP records)
- Contract CRUD (create, read, update, list with filters)
- Status transition validation (valid and invalid)
- Milestone management (create, update status, list)
- Obligation tracking (create, complete, overdue detection)
- Amendment workflows (create, list, link to parent)
- IP record management (create, get, link to contracts)
- Portfolio metrics computation
- Compliance report generation
- Auto-renewal detection
- API endpoint integration tests
- Error handling (404, 400, 422)
- Edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.contract_lifecycle import (
    AmendmentCreateRequest,
    Contract,
    ContractAmendment,
    ContractComplianceReport,
    ContractCreateRequest,
    ContractListResponse,
    ContractMetrics,
    ContractMilestone,
    ContractObligation,
    ContractParty,
    ContractStatus,
    ContractType,
    ContractUpdateRequest,
    IPRecord,
    IPRecordCreateRequest,
    IPRecordListResponse,
    IPType,
    MilestoneCreateRequest,
    MilestoneStatus,
    ObligationCreateRequest,
    ObligationType,
    RiskLevel,
)
from app.services.contract_lifecycle_service import (
    VALID_TRANSITIONS,
    ContractLifecycleService,
    get_contract_lifecycle_service,
    reset_contract_lifecycle_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/contract-lifecycle"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_contract_lifecycle_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ContractLifecycleService:
    """Shorthand for the fresh service."""
    return fresh_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract_create(**kwargs) -> ContractCreateRequest:
    """Helper to build a ContractCreateRequest with defaults."""
    defaults = dict(
        title="Test Contract",
        contract_type=ContractType.NDA,
        description="A test contract for unit testing",
        parties=[
            ContractParty(
                name="Test Corp",
                role="Client",
                contact_email="test@testcorp.com",
                organization="Test Corp",
            ),
        ],
        total_value=100000.0,
        risk_level=RiskLevel.LOW,
        tags=["test"],
    )
    defaults.update(kwargs)
    return ContractCreateRequest(**defaults)


def _make_milestone_create(**kwargs) -> MilestoneCreateRequest:
    """Helper to build a MilestoneCreateRequest with defaults."""
    defaults = dict(
        title="Test Milestone",
        description="A test milestone",
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        responsible_party="Test Corp",
        deliverable="Test deliverable",
    )
    defaults.update(kwargs)
    return MilestoneCreateRequest(**defaults)


def _make_obligation_create(**kwargs) -> ObligationCreateRequest:
    """Helper to build an ObligationCreateRequest with defaults."""
    defaults = dict(
        obligation_type=ObligationType.REPORTING,
        description="Test obligation",
        owner="Test Corp",
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        recurring=False,
    )
    defaults.update(kwargs)
    return ObligationCreateRequest(**defaults)


def _make_amendment_create(**kwargs) -> AmendmentCreateRequest:
    """Helper to build an AmendmentCreateRequest with defaults."""
    defaults = dict(
        title="Test Amendment",
        description="A test amendment",
        changes_summary="Updated terms",
        effective_date=datetime.now(timezone.utc),
        approved_by="Legal Counsel",
    )
    defaults.update(kwargs)
    return AmendmentCreateRequest(**defaults)


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify seed data is loaded correctly on service init."""

    def test_seed_contract_count(self, svc: ContractLifecycleService):
        """Seed should contain 10 contracts."""
        result = svc.list_contracts(limit=100)
        assert result.total == 10

    def test_seed_ip_record_count(self, svc: ContractLifecycleService):
        """Seed should contain 6 IP records."""
        result = svc.list_ip_records()
        assert result.total == 6

    def test_seed_contract_ids(self, svc: ContractLifecycleService):
        """Seed contracts should have sequential IDs CTR-001 through CTR-010."""
        for i in range(1, 11):
            c = svc.get_contract(f"CTR-{i:03d}")
            assert c is not None, f"CTR-{i:03d} should exist"

    def test_seed_ip_record_ids(self, svc: ContractLifecycleService):
        """Seed IP records should have IDs IP-001 through IP-006."""
        for i in range(1, 7):
            ip = svc.get_ip_record(f"IP-{i:03d}")
            assert ip is not None, f"IP-{i:03d} should exist"

    def test_seed_msa_regeneron(self, svc: ContractLifecycleService):
        """CTR-001 should be the Regeneron MSA."""
        c = svc.get_contract("CTR-001")
        assert c is not None
        assert c.contract_type == ContractType.MASTER_SERVICE
        assert c.status == ContractStatus.ACTIVE
        assert "Regeneron" in c.title
        assert c.total_value == 2400000.0

    def test_seed_baa_metriport(self, svc: ContractLifecycleService):
        """CTR-002 should be the Metriport BAA."""
        c = svc.get_contract("CTR-002")
        assert c is not None
        assert c.contract_type == ContractType.BAA
        assert c.status == ContractStatus.ACTIVE
        assert c.risk_level == RiskLevel.CRITICAL

    def test_seed_clinical_trial_eylea(self, svc: ContractLifecycleService):
        """CTR-003 should be the EYLEA HD clinical trial agreement."""
        c = svc.get_contract("CTR-003")
        assert c is not None
        assert c.contract_type == ContractType.CLINICAL_TRIAL
        assert "EYLEA" in c.title

    def test_seed_data_use_rwe(self, svc: ContractLifecycleService):
        """CTR-004 should be the RWE Data Use Agreement."""
        c = svc.get_contract("CTR-004")
        assert c is not None
        assert c.contract_type == ContractType.DATA_USE

    def test_seed_nda_cro(self, svc: ContractLifecycleService):
        """CTR-005 should be the CRO NDA."""
        c = svc.get_contract("CTR-005")
        assert c is not None
        assert c.contract_type == ContractType.NDA

    def test_seed_expired_sow(self, svc: ContractLifecycleService):
        """CTR-006 should be the expired SOW."""
        c = svc.get_contract("CTR-006")
        assert c is not None
        assert c.contract_type == ContractType.STATEMENT_OF_WORK
        assert c.status == ContractStatus.EXPIRED

    def test_seed_licensing_negotiation(self, svc: ContractLifecycleService):
        """CTR-007 should be in NEGOTIATION status."""
        c = svc.get_contract("CTR-007")
        assert c is not None
        assert c.contract_type == ContractType.LICENSING
        assert c.status == ContractStatus.NEGOTIATION

    def test_seed_amendment(self, svc: ContractLifecycleService):
        """CTR-008 should be the MSA amendment."""
        c = svc.get_contract("CTR-008")
        assert c is not None
        assert c.contract_type == ContractType.AMENDMENT
        assert c.status == ContractStatus.ACTIVE

    def test_seed_msa_has_amendment(self, svc: ContractLifecycleService):
        """CTR-001 (MSA) should contain the LIBTAYO amendment."""
        c = svc.get_contract("CTR-001")
        assert c is not None
        assert len(c.amendments) >= 1
        assert any("LIBTAYO" in a.title for a in c.amendments)

    def test_seed_milestones_present(self, svc: ContractLifecycleService):
        """CTR-001 should have 3 milestones."""
        c = svc.get_contract("CTR-001")
        assert c is not None
        assert len(c.milestones) == 3

    def test_seed_obligations_present(self, svc: ContractLifecycleService):
        """CTR-001 should have 3 obligations."""
        c = svc.get_contract("CTR-001")
        assert c is not None
        assert len(c.obligations) == 3

    def test_seed_ip_patent(self, svc: ContractLifecycleService):
        """IP-001 should be a patent."""
        ip = svc.get_ip_record("IP-001")
        assert ip is not None
        assert ip.ip_type == IPType.PATENT

    def test_seed_ip_trade_secret(self, svc: ContractLifecycleService):
        """IP-002 should be a trade secret."""
        ip = svc.get_ip_record("IP-002")
        assert ip is not None
        assert ip.ip_type == IPType.TRADE_SECRET

    def test_seed_ip_trademark(self, svc: ContractLifecycleService):
        """IP-003 should be a trademark."""
        ip = svc.get_ip_record("IP-003")
        assert ip is not None
        assert ip.ip_type == IPType.TRADEMARK

    def test_seed_ip_copyright(self, svc: ContractLifecycleService):
        """IP-004 should be a copyright."""
        ip = svc.get_ip_record("IP-004")
        assert ip is not None
        assert ip.ip_type == IPType.COPYRIGHT

    def test_seed_ip_invention_disclosure(self, svc: ContractLifecycleService):
        """IP-005 should be an invention disclosure."""
        ip = svc.get_ip_record("IP-005")
        assert ip is not None
        assert ip.ip_type == IPType.INVENTION_DISCLOSURE

    def test_seed_dupixent_trial(self, svc: ContractLifecycleService):
        """CTR-010 should be the DUPIXENT clinical trial."""
        c = svc.get_contract("CTR-010")
        assert c is not None
        assert c.contract_type == ContractType.CLINICAL_TRIAL
        assert "DUPIXENT" in c.title

    def test_seed_parties_populated(self, svc: ContractLifecycleService):
        """All seed contracts should have at least one party."""
        result = svc.list_contracts(limit=100)
        for c in result.items:
            assert len(c.parties) >= 1, f"{c.id} should have parties"


# ===========================================================================
# Section 2: Contract CRUD
# ===========================================================================


class TestContractCRUD:
    """Test contract create, read, update, list operations."""

    def test_create_contract(self, svc: ContractLifecycleService):
        """Create a basic contract."""
        req = _make_contract_create()
        c = svc.create_contract(req)
        assert c.id.startswith("CTR-")
        assert c.title == "Test Contract"
        assert c.status == ContractStatus.DRAFT
        assert c.contract_type == ContractType.NDA

    def test_create_contract_with_parties(self, svc: ContractLifecycleService):
        """Contract should store parties correctly."""
        req = _make_contract_create(
            parties=[
                ContractParty(
                    name="Alpha Corp", role="Sponsor",
                    contact_email="a@alpha.com", organization="Alpha",
                ),
                ContractParty(
                    name="Beta Inc", role="CRO",
                    contact_email="b@beta.com", organization="Beta",
                ),
            ]
        )
        c = svc.create_contract(req)
        assert len(c.parties) == 2
        assert c.parties[0].name == "Alpha Corp"

    def test_get_contract(self, svc: ContractLifecycleService):
        """Get contract by ID."""
        c = svc.get_contract("CTR-001")
        assert c is not None
        assert c.id == "CTR-001"

    def test_get_contract_not_found(self, svc: ContractLifecycleService):
        """Get non-existent contract returns None."""
        assert svc.get_contract("CTR-999") is None

    def test_update_contract_title(self, svc: ContractLifecycleService):
        """Update contract title."""
        req = ContractUpdateRequest(title="Updated Title")
        c = svc.update_contract("CTR-001", req)
        assert c is not None
        assert c.title == "Updated Title"

    def test_update_contract_description(self, svc: ContractLifecycleService):
        """Update contract description."""
        req = ContractUpdateRequest(description="New description")
        c = svc.update_contract("CTR-001", req)
        assert c is not None
        assert c.description == "New description"

    def test_update_contract_not_found(self, svc: ContractLifecycleService):
        """Update non-existent contract returns None."""
        req = ContractUpdateRequest(title="X")
        assert svc.update_contract("CTR-999", req) is None

    def test_list_contracts_default(self, svc: ContractLifecycleService):
        """List contracts without filters returns all."""
        result = svc.list_contracts()
        assert result.total == 10

    def test_list_contracts_by_type(self, svc: ContractLifecycleService):
        """Filter contracts by type."""
        result = svc.list_contracts(contract_type=ContractType.NDA)
        assert result.total >= 2
        for c in result.items:
            assert c.contract_type == ContractType.NDA

    def test_list_contracts_by_status(self, svc: ContractLifecycleService):
        """Filter contracts by status."""
        result = svc.list_contracts(status=ContractStatus.ACTIVE)
        assert result.total >= 5
        for c in result.items:
            assert c.status == ContractStatus.ACTIVE

    def test_list_contracts_by_party(self, svc: ContractLifecycleService):
        """Filter contracts by party name."""
        result = svc.list_contracts(party_name="Regeneron")
        assert result.total >= 3
        for c in result.items:
            assert any("Regeneron" in p.organization for p in c.parties)

    def test_list_contracts_pagination(self, svc: ContractLifecycleService):
        """Pagination works correctly."""
        result = svc.list_contracts(limit=3, offset=0)
        assert len(result.items) == 3
        assert result.limit == 3
        assert result.offset == 0
        assert result.total == 10

    def test_list_contracts_offset(self, svc: ContractLifecycleService):
        """Offset skips contracts."""
        result = svc.list_contracts(limit=3, offset=8)
        assert len(result.items) == 2  # 10 total, offset 8 = 2 remaining

    def test_delete_draft_contract(self, svc: ContractLifecycleService):
        """Delete a DRAFT contract."""
        req = _make_contract_create()
        c = svc.create_contract(req)
        assert svc.delete_contract(c.id) is True
        assert svc.get_contract(c.id) is None

    def test_delete_active_contract_fails(self, svc: ContractLifecycleService):
        """Deleting an ACTIVE contract raises ValueError."""
        with pytest.raises(ValueError, match="Only DRAFT"):
            svc.delete_contract("CTR-001")  # ACTIVE

    def test_delete_nonexistent_contract(self, svc: ContractLifecycleService):
        """Deleting non-existent contract returns False."""
        assert svc.delete_contract("CTR-999") is False

    def test_create_increments_id(self, svc: ContractLifecycleService):
        """Each new contract gets the next sequential ID."""
        c1 = svc.create_contract(_make_contract_create(title="A"))
        c2 = svc.create_contract(_make_contract_create(title="B"))
        # IDs should differ and be sequential
        assert c1.id != c2.id

    def test_update_tags(self, svc: ContractLifecycleService):
        """Update contract tags."""
        req = ContractUpdateRequest(tags=["new-tag", "pharma"])
        c = svc.update_contract("CTR-001", req)
        assert c is not None
        assert "new-tag" in c.tags

    def test_update_risk_level(self, svc: ContractLifecycleService):
        """Update risk level."""
        req = ContractUpdateRequest(risk_level=RiskLevel.CRITICAL)
        c = svc.update_contract("CTR-001", req)
        assert c is not None
        assert c.risk_level == RiskLevel.CRITICAL


# ===========================================================================
# Section 3: Status transition validation
# ===========================================================================


class TestStatusTransitions:
    """Test contract status transition rules."""

    def test_draft_to_review(self, svc: ContractLifecycleService):
        """DRAFT -> REVIEW is valid."""
        c = svc.create_contract(_make_contract_create())
        result = svc.transition_status(c.id, ContractStatus.REVIEW)
        assert result is not None
        assert result.status == ContractStatus.REVIEW

    def test_review_to_negotiation(self, svc: ContractLifecycleService):
        """REVIEW -> NEGOTIATION is valid."""
        c = svc.create_contract(_make_contract_create())
        svc.transition_status(c.id, ContractStatus.REVIEW)
        result = svc.transition_status(c.id, ContractStatus.NEGOTIATION)
        assert result is not None
        assert result.status == ContractStatus.NEGOTIATION

    def test_negotiation_to_pending_signature(self, svc: ContractLifecycleService):
        """NEGOTIATION -> PENDING_SIGNATURE is valid."""
        c = svc.create_contract(_make_contract_create())
        svc.transition_status(c.id, ContractStatus.REVIEW)
        svc.transition_status(c.id, ContractStatus.NEGOTIATION)
        result = svc.transition_status(c.id, ContractStatus.PENDING_SIGNATURE)
        assert result is not None
        assert result.status == ContractStatus.PENDING_SIGNATURE

    def test_pending_signature_to_active(self, svc: ContractLifecycleService):
        """PENDING_SIGNATURE -> ACTIVE is valid and sets signed_date."""
        c = svc.create_contract(_make_contract_create())
        svc.transition_status(c.id, ContractStatus.REVIEW)
        svc.transition_status(c.id, ContractStatus.NEGOTIATION)
        svc.transition_status(c.id, ContractStatus.PENDING_SIGNATURE)
        result = svc.transition_status(c.id, ContractStatus.ACTIVE)
        assert result is not None
        assert result.status == ContractStatus.ACTIVE
        assert result.signed_date is not None

    def test_active_to_expired(self, svc: ContractLifecycleService):
        """ACTIVE -> EXPIRED is valid."""
        result = svc.transition_status("CTR-001", ContractStatus.EXPIRED)
        assert result is not None
        assert result.status == ContractStatus.EXPIRED

    def test_active_to_terminated(self, svc: ContractLifecycleService):
        """ACTIVE -> TERMINATED is valid and sets terminated_date."""
        result = svc.transition_status("CTR-001", ContractStatus.TERMINATED)
        assert result is not None
        assert result.status == ContractStatus.TERMINATED
        assert result.terminated_date is not None

    def test_active_to_suspended(self, svc: ContractLifecycleService):
        """ACTIVE -> SUSPENDED is valid."""
        result = svc.transition_status("CTR-001", ContractStatus.SUSPENDED)
        assert result is not None
        assert result.status == ContractStatus.SUSPENDED

    def test_active_to_renewed(self, svc: ContractLifecycleService):
        """ACTIVE -> RENEWED is valid."""
        result = svc.transition_status("CTR-001", ContractStatus.RENEWED)
        assert result is not None
        assert result.status == ContractStatus.RENEWED

    def test_suspended_to_active(self, svc: ContractLifecycleService):
        """SUSPENDED -> ACTIVE is valid."""
        svc.transition_status("CTR-001", ContractStatus.SUSPENDED)
        result = svc.transition_status("CTR-001", ContractStatus.ACTIVE)
        assert result is not None
        assert result.status == ContractStatus.ACTIVE

    def test_suspended_to_terminated(self, svc: ContractLifecycleService):
        """SUSPENDED -> TERMINATED is valid."""
        svc.transition_status("CTR-001", ContractStatus.SUSPENDED)
        result = svc.transition_status("CTR-001", ContractStatus.TERMINATED)
        assert result is not None
        assert result.status == ContractStatus.TERMINATED

    def test_renewed_to_active(self, svc: ContractLifecycleService):
        """RENEWED -> ACTIVE is valid."""
        svc.transition_status("CTR-001", ContractStatus.RENEWED)
        result = svc.transition_status("CTR-001", ContractStatus.ACTIVE)
        assert result is not None
        assert result.status == ContractStatus.ACTIVE

    def test_invalid_draft_to_active(self, svc: ContractLifecycleService):
        """DRAFT -> ACTIVE is invalid (must go through review/negotiation)."""
        c = svc.create_contract(_make_contract_create())
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.transition_status(c.id, ContractStatus.ACTIVE)

    def test_invalid_active_to_draft(self, svc: ContractLifecycleService):
        """ACTIVE -> DRAFT is invalid."""
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.transition_status("CTR-001", ContractStatus.DRAFT)

    def test_invalid_expired_to_active(self, svc: ContractLifecycleService):
        """EXPIRED -> anything is invalid."""
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.transition_status("CTR-006", ContractStatus.ACTIVE)

    def test_invalid_terminated_to_active(self, svc: ContractLifecycleService):
        """TERMINATED -> anything is invalid."""
        svc.transition_status("CTR-001", ContractStatus.TERMINATED)
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.transition_status("CTR-001", ContractStatus.ACTIVE)

    def test_transition_not_found(self, svc: ContractLifecycleService):
        """Transition on non-existent contract returns None."""
        result = svc.transition_status("CTR-999", ContractStatus.REVIEW)
        assert result is None

    def test_review_to_draft_valid(self, svc: ContractLifecycleService):
        """REVIEW -> DRAFT is valid (send back for edits)."""
        c = svc.create_contract(_make_contract_create())
        svc.transition_status(c.id, ContractStatus.REVIEW)
        result = svc.transition_status(c.id, ContractStatus.DRAFT)
        assert result is not None
        assert result.status == ContractStatus.DRAFT

    def test_negotiation_to_review_valid(self, svc: ContractLifecycleService):
        """NEGOTIATION -> REVIEW is valid (send back for re-review)."""
        result = svc.transition_status("CTR-007", ContractStatus.REVIEW)
        assert result is not None
        assert result.status == ContractStatus.REVIEW

    def test_update_with_invalid_transition(self, svc: ContractLifecycleService):
        """Update contract with invalid status transition raises ValueError."""
        req = ContractUpdateRequest(status=ContractStatus.DRAFT)
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.update_contract("CTR-001", req)  # ACTIVE -> DRAFT


# ===========================================================================
# Section 4: Milestone management
# ===========================================================================


class TestMilestones:
    """Test milestone create, update, and list operations."""

    def test_create_milestone(self, svc: ContractLifecycleService):
        """Create a milestone on an existing contract."""
        req = _make_milestone_create()
        ms = svc.create_milestone("CTR-001", req)
        assert ms is not None
        assert ms.id.startswith("MS-")
        assert ms.status == MilestoneStatus.PENDING

    def test_create_milestone_not_found(self, svc: ContractLifecycleService):
        """Create milestone on non-existent contract returns None."""
        req = _make_milestone_create()
        assert svc.create_milestone("CTR-999", req) is None

    def test_list_milestones(self, svc: ContractLifecycleService):
        """List milestones for a contract."""
        milestones = svc.list_milestones("CTR-001")
        assert len(milestones) == 3

    def test_list_milestones_empty(self, svc: ContractLifecycleService):
        """List milestones for non-existent contract returns empty list."""
        assert svc.list_milestones("CTR-999") == []

    def test_get_milestone(self, svc: ContractLifecycleService):
        """Get a specific milestone."""
        ms = svc.get_milestone("CTR-001", "MS-001")
        assert ms is not None
        assert ms.id == "MS-001"

    def test_get_milestone_not_found(self, svc: ContractLifecycleService):
        """Get non-existent milestone returns None."""
        assert svc.get_milestone("CTR-001", "MS-999") is None

    def test_update_milestone_to_completed(self, svc: ContractLifecycleService):
        """Update milestone to COMPLETED sets completion_date."""
        ms = svc.update_milestone_status(
            "CTR-001", "MS-002", MilestoneStatus.COMPLETED
        )
        assert ms is not None
        assert ms.status == MilestoneStatus.COMPLETED
        assert ms.completion_date is not None

    def test_update_milestone_to_in_progress(self, svc: ContractLifecycleService):
        """Update milestone to IN_PROGRESS."""
        ms = svc.update_milestone_status(
            "CTR-001", "MS-003", MilestoneStatus.IN_PROGRESS
        )
        assert ms is not None
        assert ms.status == MilestoneStatus.IN_PROGRESS

    def test_update_milestone_to_waived(self, svc: ContractLifecycleService):
        """Update milestone to WAIVED."""
        ms = svc.update_milestone_status(
            "CTR-001", "MS-003", MilestoneStatus.WAIVED
        )
        assert ms is not None
        assert ms.status == MilestoneStatus.WAIVED

    def test_update_milestone_not_found_contract(self, svc: ContractLifecycleService):
        """Update milestone on non-existent contract returns None."""
        result = svc.update_milestone_status("CTR-999", "MS-001", MilestoneStatus.COMPLETED)
        assert result is None

    def test_update_milestone_not_found_milestone(self, svc: ContractLifecycleService):
        """Update non-existent milestone returns None."""
        result = svc.update_milestone_status("CTR-001", "MS-999", MilestoneStatus.COMPLETED)
        assert result is None

    def test_milestone_id_increments(self, svc: ContractLifecycleService):
        """Each new milestone gets the next sequential ID."""
        ms1 = svc.create_milestone("CTR-001", _make_milestone_create(title="A"))
        ms2 = svc.create_milestone("CTR-001", _make_milestone_create(title="B"))
        assert ms1 is not None
        assert ms2 is not None
        assert ms1.id != ms2.id


# ===========================================================================
# Section 5: Obligation tracking
# ===========================================================================


class TestObligations:
    """Test obligation create, complete, and overdue detection."""

    def test_create_obligation(self, svc: ContractLifecycleService):
        """Create an obligation on an existing contract."""
        req = _make_obligation_create()
        obl = svc.create_obligation("CTR-001", req)
        assert obl is not None
        assert obl.id.startswith("OBL-")
        assert obl.status == MilestoneStatus.PENDING

    def test_create_obligation_not_found(self, svc: ContractLifecycleService):
        """Create obligation on non-existent contract returns None."""
        req = _make_obligation_create()
        assert svc.create_obligation("CTR-999", req) is None

    def test_create_recurring_obligation(self, svc: ContractLifecycleService):
        """Create a recurring obligation."""
        req = _make_obligation_create(recurring=True, frequency_days=30)
        obl = svc.create_obligation("CTR-001", req)
        assert obl is not None
        assert obl.recurring is True
        assert obl.frequency_days == 30

    def test_list_obligations(self, svc: ContractLifecycleService):
        """List obligations for a contract."""
        obls = svc.list_obligations("CTR-001")
        assert len(obls) == 3

    def test_list_obligations_empty(self, svc: ContractLifecycleService):
        """List obligations for non-existent contract returns empty list."""
        assert svc.list_obligations("CTR-999") == []

    def test_get_obligation(self, svc: ContractLifecycleService):
        """Get a specific obligation."""
        obl = svc.get_obligation("CTR-001", "OBL-001")
        assert obl is not None
        assert obl.id == "OBL-001"

    def test_get_obligation_not_found(self, svc: ContractLifecycleService):
        """Get non-existent obligation returns None."""
        assert svc.get_obligation("CTR-001", "OBL-999") is None

    def test_complete_obligation(self, svc: ContractLifecycleService):
        """Complete an obligation sets status and last_completed."""
        obl = svc.complete_obligation("CTR-001", "OBL-001")
        assert obl is not None
        assert obl.status == MilestoneStatus.COMPLETED
        assert obl.last_completed is not None

    def test_complete_obligation_not_found(self, svc: ContractLifecycleService):
        """Complete non-existent obligation returns None."""
        assert svc.complete_obligation("CTR-001", "OBL-999") is None

    def test_complete_obligation_not_found_contract(self, svc: ContractLifecycleService):
        """Complete obligation on non-existent contract returns None."""
        assert svc.complete_obligation("CTR-999", "OBL-001") is None

    def test_overdue_obligations_detected(self, svc: ContractLifecycleService):
        """Overdue obligations should be detected."""
        overdue = svc.get_overdue_obligations()
        assert len(overdue) >= 1
        for obl in overdue:
            assert obl.status == MilestoneStatus.OVERDUE

    def test_overdue_skips_terminated_contracts(self, svc: ContractLifecycleService):
        """Overdue detection should skip terminated contracts."""
        # Terminate a contract with overdue obligations
        svc.transition_status("CTR-004", ContractStatus.TERMINATED)
        overdue = svc.get_overdue_obligations()
        # CTR-004 obligations should not appear
        ctr004_obls = [o for o in overdue if o.contract_id == "CTR-004"]
        assert len(ctr004_obls) == 0

    def test_obligation_id_increments(self, svc: ContractLifecycleService):
        """Each new obligation gets the next sequential ID."""
        o1 = svc.create_obligation("CTR-001", _make_obligation_create(description="A"))
        o2 = svc.create_obligation("CTR-001", _make_obligation_create(description="B"))
        assert o1 is not None
        assert o2 is not None
        assert o1.id != o2.id


# ===========================================================================
# Section 6: Amendment workflows
# ===========================================================================


class TestAmendments:
    """Test amendment creation and listing."""

    def test_create_amendment(self, svc: ContractLifecycleService):
        """Create an amendment on an existing contract."""
        req = _make_amendment_create()
        amd = svc.create_amendment("CTR-001", req)
        assert amd is not None
        assert amd.id.startswith("AMD-")
        assert amd.contract_id == "CTR-001"

    def test_create_amendment_not_found(self, svc: ContractLifecycleService):
        """Create amendment on non-existent contract returns None."""
        req = _make_amendment_create()
        assert svc.create_amendment("CTR-999", req) is None

    def test_list_amendments(self, svc: ContractLifecycleService):
        """List amendments for CTR-001 (should have at least 1 seed amendment)."""
        amds = svc.list_amendments("CTR-001")
        assert len(amds) >= 1

    def test_list_amendments_empty_contract(self, svc: ContractLifecycleService):
        """List amendments for contract with no amendments."""
        amds = svc.list_amendments("CTR-005")
        assert len(amds) == 0

    def test_list_amendments_not_found(self, svc: ContractLifecycleService):
        """List amendments for non-existent contract returns empty."""
        assert svc.list_amendments("CTR-999") == []

    def test_amendment_linked_to_contract(self, svc: ContractLifecycleService):
        """Creating amendment adds it to contract's amendments list."""
        before = len(svc.list_amendments("CTR-001"))
        svc.create_amendment("CTR-001", _make_amendment_create(title="New Amendment"))
        after = len(svc.list_amendments("CTR-001"))
        assert after == before + 1

    def test_amendment_has_created_at(self, svc: ContractLifecycleService):
        """Amendment should have a created_at timestamp."""
        req = _make_amendment_create()
        amd = svc.create_amendment("CTR-001", req)
        assert amd is not None
        assert amd.created_at is not None

    def test_amendment_id_increments(self, svc: ContractLifecycleService):
        """Each new amendment gets the next sequential ID."""
        a1 = svc.create_amendment("CTR-001", _make_amendment_create(title="A"))
        a2 = svc.create_amendment("CTR-001", _make_amendment_create(title="B"))
        assert a1 is not None
        assert a2 is not None
        assert a1.id != a2.id


# ===========================================================================
# Section 7: IP record management
# ===========================================================================


class TestIPRecords:
    """Test IP record CRUD and contract linking."""

    def test_list_ip_records(self, svc: ContractLifecycleService):
        """List all IP records."""
        result = svc.list_ip_records()
        assert result.total == 6

    def test_get_ip_record(self, svc: ContractLifecycleService):
        """Get an IP record by ID."""
        ip = svc.get_ip_record("IP-001")
        assert ip is not None
        assert ip.id == "IP-001"

    def test_get_ip_record_not_found(self, svc: ContractLifecycleService):
        """Get non-existent IP record returns None."""
        assert svc.get_ip_record("IP-999") is None

    def test_create_ip_record(self, svc: ContractLifecycleService):
        """Create a new IP record."""
        req = IPRecordCreateRequest(
            title="New Algorithm",
            ip_type=IPType.PATENT,
            description="A new algorithm",
            owner="BrainStorm Health",
        )
        ip = svc.create_ip_record(req)
        assert ip.id.startswith("IP-")
        assert ip.title == "New Algorithm"
        assert ip.ip_type == IPType.PATENT

    def test_link_ip_to_contract(self, svc: ContractLifecycleService):
        """Link an IP record to a contract."""
        ip = svc.link_ip_to_contract("IP-003", "CTR-003")
        assert ip is not None
        assert "CTR-003" in ip.related_contracts
        # Also check contract side
        c = svc.get_contract("CTR-003")
        assert c is not None
        assert "IP-003" in c.ip_records

    def test_link_ip_idempotent(self, svc: ContractLifecycleService):
        """Linking the same IP to the same contract twice is idempotent."""
        svc.link_ip_to_contract("IP-003", "CTR-003")
        ip = svc.link_ip_to_contract("IP-003", "CTR-003")
        assert ip is not None
        assert ip.related_contracts.count("CTR-003") == 1

    def test_link_ip_not_found_ip(self, svc: ContractLifecycleService):
        """Link with non-existent IP returns None."""
        assert svc.link_ip_to_contract("IP-999", "CTR-001") is None

    def test_link_ip_not_found_contract(self, svc: ContractLifecycleService):
        """Link with non-existent contract returns None."""
        assert svc.link_ip_to_contract("IP-001", "CTR-999") is None

    def test_ip_related_contracts(self, svc: ContractLifecycleService):
        """IP-001 should be related to CTR-001 and CTR-007."""
        ip = svc.get_ip_record("IP-001")
        assert ip is not None
        assert "CTR-001" in ip.related_contracts
        assert "CTR-007" in ip.related_contracts


# ===========================================================================
# Section 8: Metrics and compliance reports
# ===========================================================================


class TestMetrics:
    """Test portfolio metrics computation."""

    def test_metrics_total_contracts(self, svc: ContractLifecycleService):
        """Total contracts count."""
        m = svc.get_metrics()
        assert m.total_contracts == 10

    def test_metrics_by_status(self, svc: ContractLifecycleService):
        """Metrics should include by-status breakdown."""
        m = svc.get_metrics()
        assert "ACTIVE" in m.by_status
        assert m.by_status["ACTIVE"] >= 5

    def test_metrics_by_type(self, svc: ContractLifecycleService):
        """Metrics should include by-type breakdown."""
        m = svc.get_metrics()
        assert "MASTER_SERVICE" in m.by_type
        assert "BAA" in m.by_type
        assert "CLINICAL_TRIAL" in m.by_type

    def test_metrics_total_value(self, svc: ContractLifecycleService):
        """Total value should sum all contract values."""
        m = svc.get_metrics()
        assert m.total_value > 0

    def test_metrics_expiring_soon(self, svc: ContractLifecycleService):
        """Some contracts should be flagged as expiring soon."""
        m = svc.get_metrics()
        assert m.expiring_soon >= 1

    def test_metrics_overdue_milestones(self, svc: ContractLifecycleService):
        """Should detect overdue milestones."""
        m = svc.get_metrics()
        assert m.overdue_milestones >= 1

    def test_metrics_overdue_obligations(self, svc: ContractLifecycleService):
        """Should detect overdue obligations."""
        m = svc.get_metrics()
        assert m.overdue_obligations >= 1

    def test_metrics_active_ip(self, svc: ContractLifecycleService):
        """Should count active IP records."""
        m = svc.get_metrics()
        assert m.active_ip_records >= 3


class TestComplianceReport:
    """Test compliance report generation."""

    def test_compliance_report_generated(self, svc: ContractLifecycleService):
        """Report should be generated with a timestamp."""
        report = svc.get_compliance_report()
        assert report.generated_at is not None

    def test_compliance_overdue_obligations(self, svc: ContractLifecycleService):
        """Report should identify contracts with overdue obligations."""
        report = svc.get_compliance_report()
        assert len(report.contracts_with_overdue_obligations) >= 1

    def test_compliance_approaching_expiry(self, svc: ContractLifecycleService):
        """Report should identify contracts approaching expiry."""
        report = svc.get_compliance_report()
        assert len(report.approaching_expiry) >= 1

    def test_compliance_auto_renewal_pending(self, svc: ContractLifecycleService):
        """Report should identify auto-renewal candidates."""
        report = svc.get_compliance_report()
        # CTR-009 has auto_renew=True and expiry within notice window
        assert len(report.auto_renewal_pending) >= 1

    def test_compliance_total_issues(self, svc: ContractLifecycleService):
        """Total issues should be sum of all issue categories."""
        report = svc.get_compliance_report()
        expected = (
            len(report.contracts_with_overdue_obligations)
            + len(report.unsigned_past_due)
            + len(report.approaching_expiry)
            + len(report.auto_renewal_pending)
        )
        assert report.total_issues == expected


# ===========================================================================
# Section 9: Auto-renewal detection
# ===========================================================================


class TestAutoRenewal:
    """Test auto-renewal detection logic."""

    def test_auto_renewal_contracts(self, svc: ContractLifecycleService):
        """Should detect auto-renewal contracts within notice window."""
        result = svc.get_auto_renewal_contracts()
        assert len(result) >= 1

    def test_auto_renewal_only_active(self, svc: ContractLifecycleService):
        """Auto-renewal should only include ACTIVE contracts."""
        result = svc.get_auto_renewal_contracts()
        for c in result:
            assert c.status == ContractStatus.ACTIVE
            assert c.auto_renew is True

    def test_auto_renewal_excludes_non_auto(self, svc: ContractLifecycleService):
        """Contracts without auto_renew should not be included."""
        result = svc.get_auto_renewal_contracts()
        for c in result:
            assert c.auto_renew is True

    def test_auto_renewal_ctr009(self, svc: ContractLifecycleService):
        """CTR-009 should be in auto-renewal list (60-day expiry, 45-day notice)."""
        result = svc.get_auto_renewal_contracts()
        ids = [c.id for c in result]
        assert "CTR-009" in ids


# ===========================================================================
# Section 10: Service stats
# ===========================================================================


class TestServiceStats:
    """Test service health stats."""

    def test_get_stats(self, svc: ContractLifecycleService):
        """Stats should report correct counts."""
        stats = svc.get_stats()
        assert stats["total_contracts"] == 10
        assert stats["total_ip_records"] == 6


# ===========================================================================
# Section 11: API endpoint integration tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for all HTTP endpoints."""

    async def test_list_contracts_endpoint(self):
        """GET /contracts should return paginated list."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 10

    async def test_list_contracts_with_type_filter(self):
        """GET /contracts?contract_type=NDA should filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/contracts",
                params={"contract_type": "NDA"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2

    async def test_list_contracts_with_status_filter(self):
        """GET /contracts?status=ACTIVE should filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/contracts",
                params={"status": "ACTIVE"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5

    async def test_list_contracts_with_party_filter(self):
        """GET /contracts?party_name=Regeneron should filter."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/contracts",
                params={"party_name": "Regeneron"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3

    async def test_list_contracts_pagination(self):
        """GET /contracts with limit and offset."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/contracts",
                params={"limit": 3, "offset": 0},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["limit"] == 3

    async def test_get_contract_endpoint(self):
        """GET /contracts/{id} should return contract detail."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "CTR-001"

    async def test_get_contract_not_found(self):
        """GET /contracts/{id} with invalid ID returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-999")
        assert resp.status_code == 404

    async def test_create_contract_endpoint(self):
        """POST /contracts should create a new contract."""
        payload = {
            "title": "API Test Contract",
            "contract_type": "NDA",
            "description": "Created via API test",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "API Test Contract"
        assert body["status"] == "DRAFT"

    async def test_update_contract_endpoint(self):
        """PUT /contracts/{id} should update contract."""
        payload = {"title": "Updated via API"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/contracts/CTR-001", json=payload
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated via API"

    async def test_update_contract_not_found(self):
        """PUT /contracts/{id} with invalid ID returns 404."""
        payload = {"title": "X"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/contracts/CTR-999", json=payload
            )
        assert resp.status_code == 404

    async def test_update_contract_invalid_transition(self):
        """PUT /contracts/{id} with invalid status transition returns 400."""
        payload = {"status": "DRAFT"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/contracts/CTR-001", json=payload
            )
        assert resp.status_code == 400

    async def test_delete_contract_endpoint(self):
        """DELETE /contracts/{id} should delete draft contract."""
        # First create a draft
        payload = {"title": "To Delete", "contract_type": "NDA"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            create_resp = await client.post(f"{API_PREFIX}/contracts", json=payload)
            ctr_id = create_resp.json()["id"]
            resp = await client.delete(f"{API_PREFIX}/contracts/{ctr_id}")
        assert resp.status_code == 204

    async def test_delete_active_contract_returns_400(self):
        """DELETE /contracts/{id} on active contract returns 400."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/contracts/CTR-001")
        assert resp.status_code == 400

    async def test_delete_not_found_returns_404(self):
        """DELETE /contracts/{id} on non-existent contract returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/contracts/CTR-999")
        assert resp.status_code == 404

    async def test_transition_endpoint(self):
        """POST /contracts/{id}/transition should transition status."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/transition",
                params={"new_status": "SUSPENDED"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUSPENDED"

    async def test_transition_invalid_returns_400(self):
        """POST /contracts/{id}/transition with invalid transition returns 400."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/transition",
                params={"new_status": "DRAFT"},
            )
        assert resp.status_code == 400

    async def test_transition_not_found_returns_404(self):
        """POST /contracts/{id}/transition on non-existent contract returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-999/transition",
                params={"new_status": "REVIEW"},
            )
        assert resp.status_code == 404

    async def test_list_milestones_endpoint(self):
        """GET /contracts/{id}/milestones should list milestones."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-001/milestones")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3

    async def test_list_milestones_not_found(self):
        """GET /contracts/{id}/milestones on non-existent contract returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-999/milestones")
        assert resp.status_code == 404

    async def test_create_milestone_endpoint(self):
        """POST /contracts/{id}/milestones should create milestone."""
        payload = {
            "title": "New Milestone",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/milestones", json=payload
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "New Milestone"

    async def test_update_milestone_endpoint(self):
        """PUT /contracts/{id}/milestones/{ms_id} should update status."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/contracts/CTR-001/milestones/MS-002",
                params={"status": "COMPLETED"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "COMPLETED"

    async def test_list_obligations_endpoint(self):
        """GET /contracts/{id}/obligations should list obligations."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-001/obligations")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3

    async def test_create_obligation_endpoint(self):
        """POST /contracts/{id}/obligations should create obligation."""
        payload = {
            "obligation_type": "FINANCIAL",
            "description": "Payment obligation",
            "owner": "Test Corp",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/obligations", json=payload
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["obligation_type"] == "FINANCIAL"

    async def test_complete_obligation_endpoint(self):
        """POST /obligations/{obl_id}/complete should complete obligation."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/obligations/OBL-001/complete"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "COMPLETED"

    async def test_overdue_obligations_endpoint(self):
        """GET /obligations/overdue should return overdue list."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/obligations/overdue")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    async def test_list_amendments_endpoint(self):
        """GET /contracts/{id}/amendments should list amendments."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/CTR-001/amendments")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 1

    async def test_create_amendment_endpoint(self):
        """POST /contracts/{id}/amendments should create amendment."""
        payload = {
            "title": "API Amendment",
            "changes_summary": "Test changes",
            "effective_date": datetime.now(timezone.utc).isoformat(),
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/contracts/CTR-001/amendments", json=payload
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "API Amendment"

    async def test_list_ip_records_endpoint(self):
        """GET /ip-records should list IP records."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/ip-records")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 6

    async def test_create_ip_record_endpoint(self):
        """POST /ip-records should create IP record."""
        payload = {
            "title": "New Patent",
            "ip_type": "PATENT",
            "owner": "BrainStorm Health",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"{API_PREFIX}/ip-records", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "New Patent"

    async def test_get_ip_record_endpoint(self):
        """GET /ip-records/{id} should return IP record."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/ip-records/IP-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "IP-001"

    async def test_get_ip_record_not_found(self):
        """GET /ip-records/{id} with invalid ID returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/ip-records/IP-999")
        assert resp.status_code == 404

    async def test_link_ip_to_contract_endpoint(self):
        """POST /ip-records/{id}/link/{ctr_id} should link IP to contract."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/ip-records/IP-003/link/CTR-003"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "CTR-003" in body["related_contracts"]

    async def test_link_ip_not_found_ip(self):
        """POST /ip-records/{id}/link/{ctr_id} with invalid IP returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/ip-records/IP-999/link/CTR-001"
            )
        assert resp.status_code == 404

    async def test_link_ip_not_found_contract(self):
        """POST /ip-records/{id}/link/{ctr_id} with invalid contract returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"{API_PREFIX}/ip-records/IP-001/link/CTR-999"
            )
        assert resp.status_code == 404

    async def test_metrics_endpoint(self):
        """GET /contracts/metrics should return portfolio metrics."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_contracts"] == 10
        assert "by_status" in body
        assert "by_type" in body

    async def test_compliance_endpoint(self):
        """GET /contracts/compliance should return compliance report."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/compliance")
        assert resp.status_code == 200
        body = resp.json()
        assert "contracts_with_overdue_obligations" in body
        assert "generated_at" in body

    async def test_auto_renewal_endpoint(self):
        """GET /contracts/auto-renewal should return auto-renewal candidates."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"{API_PREFIX}/contracts/auto-renewal")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1


# ===========================================================================
# Section 12: Edge cases
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_create_contract_minimal(self, svc: ContractLifecycleService):
        """Create contract with minimal fields."""
        req = ContractCreateRequest(
            title="Minimal", contract_type=ContractType.NDA
        )
        c = svc.create_contract(req)
        assert c.id is not None
        assert c.status == ContractStatus.DRAFT
        assert c.parties == []
        assert c.milestones == []

    def test_full_lifecycle_flow(self, svc: ContractLifecycleService):
        """Full lifecycle: DRAFT -> REVIEW -> NEGOTIATION -> PENDING_SIGNATURE -> ACTIVE -> TERMINATED."""
        c = svc.create_contract(_make_contract_create())
        assert c.status == ContractStatus.DRAFT

        c = svc.transition_status(c.id, ContractStatus.REVIEW)
        assert c.status == ContractStatus.REVIEW

        c = svc.transition_status(c.id, ContractStatus.NEGOTIATION)
        assert c.status == ContractStatus.NEGOTIATION

        c = svc.transition_status(c.id, ContractStatus.PENDING_SIGNATURE)
        assert c.status == ContractStatus.PENDING_SIGNATURE

        c = svc.transition_status(c.id, ContractStatus.ACTIVE)
        assert c.status == ContractStatus.ACTIVE
        assert c.signed_date is not None

        c = svc.transition_status(c.id, ContractStatus.TERMINATED)
        assert c.status == ContractStatus.TERMINATED
        assert c.terminated_date is not None

    def test_suspended_resume_cycle(self, svc: ContractLifecycleService):
        """ACTIVE -> SUSPENDED -> ACTIVE cycle."""
        svc.transition_status("CTR-001", ContractStatus.SUSPENDED)
        result = svc.transition_status("CTR-001", ContractStatus.ACTIVE)
        assert result is not None
        assert result.status == ContractStatus.ACTIVE

    def test_renewed_to_active_cycle(self, svc: ContractLifecycleService):
        """ACTIVE -> RENEWED -> ACTIVE cycle."""
        svc.transition_status("CTR-001", ContractStatus.RENEWED)
        result = svc.transition_status("CTR-001", ContractStatus.ACTIVE)
        assert result is not None
        assert result.status == ContractStatus.ACTIVE

    def test_multiple_amendments(self, svc: ContractLifecycleService):
        """Multiple amendments can be added to one contract."""
        for i in range(5):
            amd = svc.create_amendment(
                "CTR-001",
                _make_amendment_create(title=f"Amendment {i+1}"),
            )
            assert amd is not None

        amds = svc.list_amendments("CTR-001")
        assert len(amds) >= 6  # 1 seed + 5 new

    def test_multiple_milestones_on_contract(self, svc: ContractLifecycleService):
        """Multiple milestones can be added to one contract."""
        before = len(svc.list_milestones("CTR-001"))
        for i in range(3):
            svc.create_milestone("CTR-001", _make_milestone_create(title=f"MS {i}"))
        after = len(svc.list_milestones("CTR-001"))
        assert after == before + 3

    def test_combined_filters(self, svc: ContractLifecycleService):
        """Filter by type AND status."""
        result = svc.list_contracts(
            contract_type=ContractType.CLINICAL_TRIAL,
            status=ContractStatus.ACTIVE,
        )
        for c in result.items:
            assert c.contract_type == ContractType.CLINICAL_TRIAL
            assert c.status == ContractStatus.ACTIVE

    def test_party_filter_case_insensitive(self, svc: ContractLifecycleService):
        """Party name filter should be case-insensitive."""
        result = svc.list_contracts(party_name="regeneron")
        assert result.total >= 3

    def test_singleton_returns_same_instance(self):
        """get_contract_lifecycle_service should return same instance."""
        s1 = get_contract_lifecycle_service()
        s2 = get_contract_lifecycle_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """reset_contract_lifecycle_service should create new instance."""
        s1 = get_contract_lifecycle_service()
        s2 = reset_contract_lifecycle_service()
        assert s1 is not s2

    def test_valid_transitions_map_completeness(self):
        """Every ContractStatus should have an entry in VALID_TRANSITIONS."""
        for status in ContractStatus:
            assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"

    def test_obligation_overdue_updates_status(self, svc: ContractLifecycleService):
        """Overdue detection should update obligation status to OVERDUE."""
        overdue = svc.get_overdue_obligations()
        for obl in overdue:
            assert obl.status == MilestoneStatus.OVERDUE

    def test_ip_record_with_related_contracts(self, svc: ContractLifecycleService):
        """IP record creation with related_contracts."""
        req = IPRecordCreateRequest(
            title="Test IP",
            ip_type=IPType.PATENT,
            owner="Test Corp",
            related_contracts=["CTR-001", "CTR-002"],
        )
        ip = svc.create_ip_record(req)
        assert len(ip.related_contracts) == 2
        assert "CTR-001" in ip.related_contracts
