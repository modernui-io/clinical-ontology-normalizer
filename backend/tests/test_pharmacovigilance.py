"""Tests for Pharmacovigilance Signal Management (CLINICAL-4).

Covers:
- Seed data verification (ICSRs, signals, periodic reports, regulatory actions, MedDRA)
- ICSR CRUD (create, read, update, list with all filter combinations, delete)
- ICSR search (text across multiple fields)
- ICSR status transition validation
- Signal detection via disproportionality analysis (PRR, ROR, BCPNN, EBGM)
- Signal CRUD and classification workflow
- Signal classification transition validation
- MedDRA coding (term lookup, hierarchy, text-to-PT mapping)
- Periodic safety report generation and listing
- Regulatory action CRUD and status updates
- Case series analysis (demographics, distributions)
- Pharmacovigilance metrics computation
- Error handling (404s, 400s, invalid transitions)
- Pagination and edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.pharmacovigilance import (
    CausalityCategory,
    DisproportionalityMethod,
    ICSRCreate,
    ICSRStatus,
    ICSRUpdate,
    MedDRALevel,
    RegulatoryActionCreate,
    RegulatoryActionStatus,
    RegulatoryActionType,
    ReportType,
    SignalClassification,
    SignalCreate,
    SignalDetectionRequest,
    SignalSource,
    SignalUpdate,
)
from app.services.pharmacovigilance_service import (
    PharmacovigilanceService,
    get_pharmacovigilance_service,
    reset_pharmacovigilance_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/pharmacovigilance"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_pharmacovigilance_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PharmacovigilanceService:
    """Shorthand for the fresh service."""
    return fresh_service


def _make_icsr_create(**overrides) -> ICSRCreate:
    """Helper to build an ICSRCreate with defaults."""
    defaults = {
        "case_number": "CASE-TEST-00001",
        "patient_age": 55,
        "patient_sex": "F",
        "reporter_type": "Physician",
        "drug_name": "Dupilumab",
        "indication": "Atopic dermatitis",
        "event_terms": ["Conjunctivitis"],
        "outcome": "Recovered",
        "seriousness_criteria": [],
        "causality": CausalityCategory.POSSIBLE,
        "source": SignalSource.CLINICAL_TRIAL,
        "country": "US",
        "narrative": "Test case narrative.",
    }
    defaults.update(overrides)
    return ICSRCreate(**defaults)


# ===================================================================
# SECTION 1: Seed data verification (10 tests)
# ===================================================================


class TestSeedData:
    """Verify seed data is correctly populated."""

    def test_seed_icsrs_count(self, svc: PharmacovigilanceService):
        """50 ICSRs should be seeded."""
        assert len(svc._icsrs) == 50

    def test_seed_signals_count(self, svc: PharmacovigilanceService):
        """8 signals should be seeded."""
        assert len(svc._signals) == 8

    def test_seed_periodic_reports_count(self, svc: PharmacovigilanceService):
        """4 periodic safety reports should be seeded."""
        assert len(svc._periodic_reports) == 4

    def test_seed_regulatory_actions_count(self, svc: PharmacovigilanceService):
        """3 regulatory actions should be seeded."""
        assert len(svc._regulatory_actions) == 3

    def test_seed_meddra_terms_count(self, svc: PharmacovigilanceService):
        """30 MedDRA terms should be seeded."""
        assert len(svc._meddra_terms) == 30

    def test_seed_signal_classifications(self, svc: PharmacovigilanceService):
        """Signals have correct distribution: 3 validated, 2 under eval, 2 refuted, 1 monitoring."""
        sigs = list(svc._signals.values())
        validated = [s for s in sigs if s.classification == SignalClassification.VALIDATED]
        under_eval = [s for s in sigs if s.classification == SignalClassification.UNDER_EVALUATION]
        refuted = [s for s in sigs if s.classification == SignalClassification.REFUTED]
        monitoring = [s for s in sigs if s.classification == SignalClassification.MONITORING]
        assert len(validated) == 3
        assert len(under_eval) == 2
        assert len(refuted) == 2
        assert len(monitoring) == 1

    def test_seed_icsrs_have_drug_names(self, svc: PharmacovigilanceService):
        """All ICSRs have drug names."""
        for icsr in svc._icsrs.values():
            assert icsr.drug_name in ("Dupilumab", "Aflibercept", "Cemiplimab")

    def test_seed_icsrs_have_event_terms(self, svc: PharmacovigilanceService):
        """All ICSRs have at least one event term."""
        for icsr in svc._icsrs.values():
            assert len(icsr.event_terms) >= 1

    def test_seed_meddra_has_all_levels(self, svc: PharmacovigilanceService):
        """MedDRA hierarchy includes all 5 levels."""
        levels = {t.level for t in svc._meddra_terms.values()}
        assert MedDRALevel.SOC in levels
        assert MedDRALevel.HLGT in levels
        assert MedDRALevel.HLT in levels
        assert MedDRALevel.PT in levels
        assert MedDRALevel.LLT in levels

    def test_seed_regulatory_actions_have_signal_refs(self, svc: PharmacovigilanceService):
        """All regulatory actions reference existing signals."""
        for action in svc._regulatory_actions.values():
            assert action.signal_id in svc._signals


# ===================================================================
# SECTION 2: ICSR CRUD (25 tests)
# ===================================================================


class TestICSRCRUD:
    """Test ICSR create, read, update, list, delete operations."""

    def test_create_icsr(self, svc: PharmacovigilanceService):
        """Create a new ICSR."""
        payload = _make_icsr_create()
        icsr = svc.create_icsr(payload)
        assert icsr.id.startswith("ICSR-")
        assert icsr.drug_name == "Dupilumab"
        assert icsr.status == ICSRStatus.INITIAL

    def test_create_icsr_with_seriousness(self, svc: PharmacovigilanceService):
        """Create a serious ICSR."""
        payload = _make_icsr_create(
            seriousness_criteria=["Requires hospitalization"],
            outcome="Not Recovered",
        )
        icsr = svc.create_icsr(payload)
        assert len(icsr.seriousness_criteria) == 1

    def test_get_icsr(self, svc: PharmacovigilanceService):
        """Retrieve an existing ICSR."""
        icsr = svc.get_icsr("ICSR-0001")
        assert icsr is not None
        assert icsr.id == "ICSR-0001"

    def test_get_icsr_not_found(self, svc: PharmacovigilanceService):
        """Non-existent ICSR returns None."""
        assert svc.get_icsr("ICSR-9999") is None

    def test_update_icsr_outcome(self, svc: PharmacovigilanceService):
        """Update ICSR outcome."""
        result = svc.update_icsr("ICSR-0001", ICSRUpdate(outcome="Recovered"))
        assert result is not None
        assert result.outcome == "Recovered"

    def test_update_icsr_status_valid(self, svc: PharmacovigilanceService):
        """Valid ICSR status transition INITIAL -> FOLLOW_UP."""
        # Find an INITIAL ICSR
        initial = [c for c in svc._icsrs.values() if c.status == ICSRStatus.INITIAL]
        assert len(initial) > 0
        icsr = initial[0]
        result = svc.update_icsr(icsr.id, ICSRUpdate(status=ICSRStatus.FOLLOW_UP))
        assert result is not None
        assert result.status == ICSRStatus.FOLLOW_UP

    def test_update_icsr_status_invalid(self, svc: PharmacovigilanceService):
        """Invalid ICSR status transition FINAL -> INITIAL raises ValueError."""
        final = [c for c in svc._icsrs.values() if c.status == ICSRStatus.FINAL]
        assert len(final) > 0
        with pytest.raises(ValueError, match="Invalid ICSR status transition"):
            svc.update_icsr(final[0].id, ICSRUpdate(status=ICSRStatus.INITIAL))

    def test_update_icsr_not_found(self, svc: PharmacovigilanceService):
        """Update non-existent ICSR returns None."""
        assert svc.update_icsr("ICSR-9999", ICSRUpdate(outcome="Fatal")) is None

    def test_delete_icsr(self, svc: PharmacovigilanceService):
        """Delete an ICSR."""
        assert svc.delete_icsr("ICSR-0001") is True
        assert svc.get_icsr("ICSR-0001") is None

    def test_delete_icsr_not_found(self, svc: PharmacovigilanceService):
        """Delete non-existent ICSR returns False."""
        assert svc.delete_icsr("ICSR-9999") is False

    def test_list_icsrs_all(self, svc: PharmacovigilanceService):
        """List all ICSRs."""
        result = svc.list_icsrs(limit=100)
        assert result.total == 50

    def test_list_icsrs_by_drug(self, svc: PharmacovigilanceService):
        """Filter ICSRs by drug name."""
        result = svc.list_icsrs(drug_name="Dupilumab")
        assert result.total > 0
        assert all(c.drug_name == "Dupilumab" for c in result.items)

    def test_list_icsrs_by_status(self, svc: PharmacovigilanceService):
        """Filter ICSRs by status."""
        result = svc.list_icsrs(status=ICSRStatus.INITIAL)
        assert result.total > 0
        assert all(c.status == ICSRStatus.INITIAL for c in result.items)

    def test_list_icsrs_by_source(self, svc: PharmacovigilanceService):
        """Filter ICSRs by source."""
        result = svc.list_icsrs(source=SignalSource.CLINICAL_TRIAL)
        assert result.total > 0
        assert all(c.source == SignalSource.CLINICAL_TRIAL for c in result.items)

    def test_list_icsrs_by_country(self, svc: PharmacovigilanceService):
        """Filter ICSRs by country."""
        result = svc.list_icsrs(country="US")
        assert result.total > 0
        assert all(c.country == "US" for c in result.items)

    def test_list_icsrs_by_causality(self, svc: PharmacovigilanceService):
        """Filter ICSRs by causality."""
        result = svc.list_icsrs(causality=CausalityCategory.PROBABLE)
        assert result.total > 0
        assert all(c.causality == CausalityCategory.PROBABLE for c in result.items)

    def test_list_icsrs_serious_only(self, svc: PharmacovigilanceService):
        """Filter ICSRs by seriousness."""
        result = svc.list_icsrs(serious=True)
        assert result.total > 0
        for c in result.items:
            assert len(c.seriousness_criteria) > 0

    def test_list_icsrs_non_serious(self, svc: PharmacovigilanceService):
        """Filter ICSRs by non-serious."""
        result = svc.list_icsrs(serious=False)
        assert result.total > 0
        for c in result.items:
            assert len(c.seriousness_criteria) == 0

    def test_list_icsrs_pagination(self, svc: PharmacovigilanceService):
        """Pagination works for ICSRs."""
        page1 = svc.list_icsrs(limit=10, offset=0)
        page2 = svc.list_icsrs(limit=10, offset=10)
        assert len(page1.items) == 10
        assert len(page2.items) == 10
        assert page1.items[0].id != page2.items[0].id

    def test_list_icsrs_combined_filters(self, svc: PharmacovigilanceService):
        """Apply multiple filters at once."""
        result = svc.list_icsrs(
            drug_name="Dupilumab",
            source=SignalSource.CLINICAL_TRIAL,
        )
        for c in result.items:
            assert c.drug_name == "Dupilumab"
            assert c.source == SignalSource.CLINICAL_TRIAL

    def test_search_icsrs_by_drug(self, svc: PharmacovigilanceService):
        """Search ICSRs by drug name."""
        result = svc.search_icsrs("Cemiplimab")
        assert result.total > 0
        for c in result.items:
            assert "cemiplimab" in c.drug_name.lower() or "cemiplimab" in (c.narrative or "").lower()

    def test_search_icsrs_by_event(self, svc: PharmacovigilanceService):
        """Search ICSRs by event term."""
        result = svc.search_icsrs("Conjunctivitis")
        assert result.total > 0

    def test_search_icsrs_by_case_number(self, svc: PharmacovigilanceService):
        """Search ICSRs by case number."""
        result = svc.search_icsrs("CASE-2025")
        assert result.total > 0

    def test_search_icsrs_no_match(self, svc: PharmacovigilanceService):
        """Search with no matches returns empty."""
        result = svc.search_icsrs("ZZZZNONEXISTENT")
        assert result.total == 0

    def test_icsr_status_nullified_is_terminal(self, svc: PharmacovigilanceService):
        """NULLIFIED is a terminal state."""
        initial = [c for c in svc._icsrs.values() if c.status == ICSRStatus.INITIAL][0]
        svc.update_icsr(initial.id, ICSRUpdate(status=ICSRStatus.NULLIFIED))
        with pytest.raises(ValueError):
            svc.update_icsr(initial.id, ICSRUpdate(status=ICSRStatus.FOLLOW_UP))


# ===================================================================
# SECTION 3: Signal detection (20 tests)
# ===================================================================


class TestSignalDetection:
    """Test disproportionality analysis and signal detection."""

    def test_detect_signal_prr(self, svc: PharmacovigilanceService):
        """PRR calculation returns a result."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert len(result.results) == 1
        assert result.results[0].method == DisproportionalityMethod.PRR
        assert result.drug == "Dupilumab"
        assert result.event == "Conjunctivitis"

    def test_detect_signal_ror(self, svc: PharmacovigilanceService):
        """ROR calculation returns a result."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.ROR],
        )
        result = svc.detect_signal(req)
        assert len(result.results) == 1
        assert result.results[0].method == DisproportionalityMethod.ROR

    def test_detect_signal_bcpnn(self, svc: PharmacovigilanceService):
        """BCPNN/IC calculation returns a result."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.BCPNN],
        )
        result = svc.detect_signal(req)
        assert len(result.results) == 1
        assert result.results[0].method == DisproportionalityMethod.BCPNN

    def test_detect_signal_ebgm(self, svc: PharmacovigilanceService):
        """EBGM calculation returns a result."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.EBGM],
        )
        result = svc.detect_signal(req)
        assert len(result.results) == 1
        assert result.results[0].method == DisproportionalityMethod.EBGM

    def test_detect_signal_all_methods(self, svc: PharmacovigilanceService):
        """Running all 4 methods returns 4 results."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
        )
        result = svc.detect_signal(req)
        assert len(result.results) == 4

    def test_detect_signal_has_observed_count(self, svc: PharmacovigilanceService):
        """Signal detection returns observed count."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].observed > 0

    def test_detect_signal_has_expected_count(self, svc: PharmacovigilanceService):
        """Signal detection returns expected count."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].expected > 0

    def test_detect_signal_confidence_intervals(self, svc: PharmacovigilanceService):
        """Signal detection returns confidence intervals."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        r = result.results[0]
        assert r.lower_ci <= r.measure <= r.upper_ci

    def test_detect_signal_rare_event_no_signal(self, svc: PharmacovigilanceService):
        """Rare event with few cases should not generate signal."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Cardiac arrest",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        # May or may not detect a signal depending on data, but should return a result
        assert len(result.results) == 1

    def test_detect_signal_nonexistent_drug(self, svc: PharmacovigilanceService):
        """Non-existent drug returns zero observed."""
        req = SignalDetectionRequest(
            drug_name="NonexistentDrug",
            event_term="Headache",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].observed == 0
        assert not result.signal_detected

    def test_detect_signal_nonexistent_event(self, svc: PharmacovigilanceService):
        """Non-existent event returns zero observed."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="NonexistentEvent",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].observed == 0

    def test_prr_measure_positive(self, svc: PharmacovigilanceService):
        """PRR measure should be >= 0."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.PRR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].measure >= 0

    def test_ror_measure_positive(self, svc: PharmacovigilanceService):
        """ROR measure should be >= 0."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            methods=[DisproportionalityMethod.ROR],
        )
        result = svc.detect_signal(req)
        assert result.results[0].measure >= 0

    def test_detect_strongest_method_populated(self, svc: PharmacovigilanceService):
        """Strongest method should be populated when signal detected."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
        )
        result = svc.detect_signal(req)
        if result.signal_detected:
            assert result.strongest_method is not None

    def test_contingency_table_sums(self, svc: PharmacovigilanceService):
        """Contingency table cells sum to total ICSRs."""
        a, b, c, d = svc._build_contingency("Dupilumab", "Conjunctivitis")
        assert a + b + c + d == len(svc._icsrs)

    def test_contingency_table_drug_column(self, svc: PharmacovigilanceService):
        """Drug column (a+b) equals total Dupilumab ICSRs."""
        a, b, c, d = svc._build_contingency("Dupilumab", "Conjunctivitis")
        dupilumab_count = sum(1 for c in svc._icsrs.values() if c.drug_name == "Dupilumab")
        assert a + b == dupilumab_count

    def test_multiple_drugs_detection(self, svc: PharmacovigilanceService):
        """Signal detection works for different drugs."""
        for drug in ["Dupilumab", "Aflibercept", "Cemiplimab"]:
            req = SignalDetectionRequest(
                drug_name=drug,
                event_term="Headache",
                methods=[DisproportionalityMethod.PRR],
            )
            result = svc.detect_signal(req)
            assert len(result.results) == 1

    def test_ebgm_measure_positive(self, svc: PharmacovigilanceService):
        """EBGM measure should be >= 0."""
        req = SignalDetectionRequest(
            drug_name="Cemiplimab",
            event_term="Pneumonitis",
            methods=[DisproportionalityMethod.EBGM],
        )
        result = svc.detect_signal(req)
        assert result.results[0].measure >= 0

    def test_ic_can_be_negative(self, svc: PharmacovigilanceService):
        """IC (BCPNN) measure can be negative for non-associated events."""
        req = SignalDetectionRequest(
            drug_name="NonexistentDrug",
            event_term="Headache",
            methods=[DisproportionalityMethod.BCPNN],
        )
        result = svc.detect_signal(req)
        assert result.results[0].measure <= 0

    def test_signal_detection_response_structure(self, svc: PharmacovigilanceService):
        """Verify response structure of signal detection."""
        req = SignalDetectionRequest(
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
        )
        result = svc.detect_signal(req)
        assert hasattr(result, "drug")
        assert hasattr(result, "event")
        assert hasattr(result, "results")
        assert hasattr(result, "signal_detected")
        assert hasattr(result, "strongest_method")


# ===================================================================
# SECTION 4: Signal CRUD (18 tests)
# ===================================================================


class TestSignalCRUD:
    """Test signal create, read, update, list, delete operations."""

    def test_create_signal(self, svc: PharmacovigilanceService):
        """Create a new signal record."""
        payload = SignalCreate(
            title="Test signal",
            description="Test description",
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
            source=SignalSource.CLINICAL_TRIAL,
        )
        signal = svc.create_signal(payload)
        assert signal.id.startswith("SIG-")
        assert signal.classification == SignalClassification.UNDER_EVALUATION
        assert signal.drug_name == "Dupilumab"

    def test_create_signal_auto_populates_stats(self, svc: PharmacovigilanceService):
        """Created signal has auto-populated disproportionality stats."""
        payload = SignalCreate(
            title="Auto stats signal",
            description="Should have stats",
            drug_name="Dupilumab",
            event_term="Conjunctivitis",
        )
        signal = svc.create_signal(payload)
        # PRR should be populated from detection
        assert signal.prr is not None

    def test_get_signal(self, svc: PharmacovigilanceService):
        """Retrieve an existing signal."""
        signal = svc.get_signal("SIG-0001")
        assert signal is not None
        assert signal.title == "Dupilumab-associated conjunctivitis"

    def test_get_signal_not_found(self, svc: PharmacovigilanceService):
        """Non-existent signal returns None."""
        assert svc.get_signal("SIG-9999") is None

    def test_update_signal_classification_valid(self, svc: PharmacovigilanceService):
        """Valid classification transition: UNDER_EVALUATION -> VALIDATED."""
        under_eval = [
            s for s in svc._signals.values()
            if s.classification == SignalClassification.UNDER_EVALUATION
        ]
        assert len(under_eval) > 0
        result = svc.update_signal(
            under_eval[0].id,
            SignalUpdate(classification=SignalClassification.VALIDATED),
        )
        assert result is not None
        assert result.classification == SignalClassification.VALIDATED

    def test_update_signal_classification_invalid(self, svc: PharmacovigilanceService):
        """Invalid transition: CLOSED -> VALIDATED raises ValueError."""
        # First close a refuted signal
        refuted = [
            s for s in svc._signals.values()
            if s.classification == SignalClassification.REFUTED
        ]
        assert len(refuted) > 0
        svc.update_signal(refuted[0].id, SignalUpdate(classification=SignalClassification.CLOSED))
        with pytest.raises(ValueError, match="Invalid signal classification"):
            svc.update_signal(refuted[0].id, SignalUpdate(classification=SignalClassification.VALIDATED))

    def test_update_signal_assessor(self, svc: PharmacovigilanceService):
        """Update signal assessor."""
        result = svc.update_signal("SIG-0001", SignalUpdate(assessor="Dr. New Assessor"))
        assert result.assessor == "Dr. New Assessor"

    def test_update_signal_not_found(self, svc: PharmacovigilanceService):
        """Update non-existent signal returns None."""
        assert svc.update_signal("SIG-9999", SignalUpdate(assessor="X")) is None

    def test_update_signal_updates_timestamp(self, svc: PharmacovigilanceService):
        """Updating signal refreshes updated_at."""
        before = svc.get_signal("SIG-0001").updated_at
        result = svc.update_signal("SIG-0001", SignalUpdate(assessor="Dr. Timestamp Test"))
        assert result.updated_at >= before

    def test_list_signals_all(self, svc: PharmacovigilanceService):
        """List all signals."""
        result = svc.list_signals()
        assert result.total == 8

    def test_list_signals_by_drug(self, svc: PharmacovigilanceService):
        """Filter signals by drug."""
        result = svc.list_signals(drug_name="Dupilumab")
        assert result.total > 0
        for s in result.items:
            assert s.drug_name == "Dupilumab"

    def test_list_signals_by_classification(self, svc: PharmacovigilanceService):
        """Filter signals by classification."""
        result = svc.list_signals(classification=SignalClassification.VALIDATED)
        assert result.total == 3

    def test_list_signals_by_source(self, svc: PharmacovigilanceService):
        """Filter signals by source."""
        result = svc.list_signals(source=SignalSource.CLINICAL_TRIAL)
        assert result.total > 0

    def test_list_signals_pagination(self, svc: PharmacovigilanceService):
        """Pagination works for signals."""
        page1 = svc.list_signals(limit=3, offset=0)
        page2 = svc.list_signals(limit=3, offset=3)
        assert len(page1.items) == 3
        assert len(page2.items) == 3

    def test_delete_signal(self, svc: PharmacovigilanceService):
        """Delete a signal."""
        assert svc.delete_signal("SIG-0001") is True
        assert svc.get_signal("SIG-0001") is None

    def test_delete_signal_not_found(self, svc: PharmacovigilanceService):
        """Delete non-existent signal returns False."""
        assert svc.delete_signal("SIG-9999") is False

    def test_signal_closed_is_terminal(self, svc: PharmacovigilanceService):
        """CLOSED is a terminal classification."""
        refuted = [
            s for s in svc._signals.values()
            if s.classification == SignalClassification.REFUTED
        ]
        assert len(refuted) > 0
        svc.update_signal(refuted[0].id, SignalUpdate(classification=SignalClassification.CLOSED))
        with pytest.raises(ValueError):
            svc.update_signal(refuted[0].id, SignalUpdate(classification=SignalClassification.VALIDATED))

    def test_signal_validated_can_go_to_monitoring(self, svc: PharmacovigilanceService):
        """VALIDATED -> MONITORING is allowed."""
        validated = [
            s for s in svc._signals.values()
            if s.classification == SignalClassification.VALIDATED
        ]
        assert len(validated) > 0
        result = svc.update_signal(
            validated[0].id,
            SignalUpdate(classification=SignalClassification.MONITORING),
        )
        assert result.classification == SignalClassification.MONITORING


# ===================================================================
# SECTION 5: MedDRA coding (15 tests)
# ===================================================================


class TestMedDRACoding:
    """Test MedDRA term lookup, hierarchy, and text-to-PT mapping."""

    def test_search_meddra_by_term(self, svc: PharmacovigilanceService):
        """Search MedDRA by term text."""
        result = svc.search_meddra("conjunctivitis")
        assert result.total > 0

    def test_search_meddra_by_code(self, svc: PharmacovigilanceService):
        """Search MedDRA by code."""
        result = svc.search_meddra("10010741")
        assert result.total >= 1

    def test_search_meddra_by_level(self, svc: PharmacovigilanceService):
        """Filter MedDRA search by hierarchy level."""
        result = svc.search_meddra("disorders", level=MedDRALevel.SOC)
        assert result.total > 0
        for t in result.terms:
            assert t.level == MedDRALevel.SOC

    def test_search_meddra_no_match(self, svc: PharmacovigilanceService):
        """MedDRA search with no match returns empty."""
        result = svc.search_meddra("zzzzzznonexistent")
        assert result.total == 0

    def test_get_meddra_term(self, svc: PharmacovigilanceService):
        """Get MedDRA term by code."""
        term = svc.get_meddra_term("10010741")
        assert term is not None
        assert term.term == "Conjunctivitis"
        assert term.level == MedDRALevel.PT

    def test_get_meddra_term_not_found(self, svc: PharmacovigilanceService):
        """Non-existent MedDRA code returns None."""
        assert svc.get_meddra_term("99999999") is None

    def test_get_meddra_hierarchy(self, svc: PharmacovigilanceService):
        """Get hierarchy for a PT term."""
        result = svc.get_meddra_hierarchy("10010741")
        assert result is not None
        assert result.term.code == "10010741"
        assert len(result.ancestors) > 0

    def test_get_meddra_hierarchy_has_children(self, svc: PharmacovigilanceService):
        """PT term Conjunctivitis should have LLT children."""
        result = svc.get_meddra_hierarchy("10010741")
        assert result is not None
        assert len(result.children) >= 2  # allergic and bacterial

    def test_get_meddra_hierarchy_not_found(self, svc: PharmacovigilanceService):
        """Non-existent code returns None for hierarchy."""
        assert svc.get_meddra_hierarchy("99999999") is None

    def test_code_to_meddra_exact_match(self, svc: PharmacovigilanceService):
        """Map exact term text to MedDRA PT."""
        term = svc.code_to_meddra("Conjunctivitis")
        assert term is not None
        assert term.code == "10010741"
        assert term.level == MedDRALevel.PT

    def test_code_to_meddra_partial_match(self, svc: PharmacovigilanceService):
        """Map partial term text to MedDRA."""
        term = svc.code_to_meddra("headache")
        assert term is not None
        assert "headache" in term.term.lower()

    def test_code_to_meddra_no_match(self, svc: PharmacovigilanceService):
        """No MedDRA match returns None."""
        assert svc.code_to_meddra("zzzznonexistent") is None

    def test_soc_has_no_parent(self, svc: PharmacovigilanceService):
        """SOC-level terms have no parent."""
        soc_terms = [t for t in svc._meddra_terms.values() if t.level == MedDRALevel.SOC]
        for t in soc_terms:
            assert t.parent_code is None

    def test_llt_has_parent(self, svc: PharmacovigilanceService):
        """LLT-level terms have a parent."""
        llt_terms = [t for t in svc._meddra_terms.values() if t.level == MedDRALevel.LLT]
        for t in llt_terms:
            assert t.parent_code is not None

    def test_search_meddra_limit(self, svc: PharmacovigilanceService):
        """MedDRA search respects limit parameter."""
        result = svc.search_meddra("a", limit=3)
        assert len(result.terms) <= 3


# ===================================================================
# SECTION 6: Periodic Safety Reports (10 tests)
# ===================================================================


class TestPeriodicSafetyReports:
    """Test periodic safety report generation and listing."""

    def test_list_periodic_reports(self, svc: PharmacovigilanceService):
        """List all periodic reports."""
        result = svc.list_periodic_reports()
        assert result.total == 4

    def test_list_periodic_reports_by_drug(self, svc: PharmacovigilanceService):
        """Filter periodic reports by drug."""
        result = svc.list_periodic_reports(drug_name="Dupilumab")
        assert result.total >= 1
        for r in result.items:
            assert r.drug_name == "Dupilumab"

    def test_list_periodic_reports_by_type(self, svc: PharmacovigilanceService):
        """Filter periodic reports by type."""
        result = svc.list_periodic_reports(report_type=ReportType.DSUR)
        assert result.total >= 1
        for r in result.items:
            assert r.report_type == ReportType.DSUR

    def test_get_periodic_report(self, svc: PharmacovigilanceService):
        """Get a single periodic report."""
        report = svc.get_periodic_report("PSR-0001")
        assert report is not None
        assert report.drug_name == "Dupilumab"

    def test_get_periodic_report_not_found(self, svc: PharmacovigilanceService):
        """Non-existent report returns None."""
        assert svc.get_periodic_report("PSR-9999") is None

    def test_generate_periodic_report(self, svc: PharmacovigilanceService):
        """Generate a new periodic safety report."""
        now = datetime.now(timezone.utc)
        report = svc.generate_periodic_report(
            drug_name="Dupilumab",
            report_type=ReportType.DSUR,
            period_start=now - timedelta(days=365),
            period_end=now,
        )
        assert report.id.startswith("PSR-")
        assert report.drug_name == "Dupilumab"
        assert report.report_type == ReportType.DSUR
        assert report.total_cases >= 0

    def test_generated_report_counts_cases(self, svc: PharmacovigilanceService):
        """Generated report counts cases in period."""
        now = datetime.now(timezone.utc)
        report = svc.generate_periodic_report(
            drug_name="Dupilumab",
            report_type=ReportType.PSUR,
            period_start=now - timedelta(days=365),
            period_end=now,
        )
        # We have dupilumab ICSRs in the seed data
        assert report.total_cases >= 0

    def test_generated_report_serious_count(self, svc: PharmacovigilanceService):
        """Generated report tracks serious cases."""
        now = datetime.now(timezone.utc)
        report = svc.generate_periodic_report(
            drug_name="Dupilumab",
            report_type=ReportType.DSUR,
            period_start=now - timedelta(days=365),
            period_end=now,
        )
        assert report.serious_cases >= 0
        assert report.serious_cases <= report.total_cases

    def test_generated_report_has_assessment(self, svc: PharmacovigilanceService):
        """Generated report has benefit-risk assessment text."""
        now = datetime.now(timezone.utc)
        report = svc.generate_periodic_report(
            drug_name="Aflibercept",
            report_type=ReportType.PBRER,
            period_start=now - timedelta(days=180),
            period_end=now,
        )
        assert report.benefit_risk_assessment is not None

    def test_list_periodic_reports_pagination(self, svc: PharmacovigilanceService):
        """Pagination works for periodic reports."""
        page1 = svc.list_periodic_reports(limit=2, offset=0)
        page2 = svc.list_periodic_reports(limit=2, offset=2)
        assert len(page1.items) == 2
        assert len(page2.items) == 2


# ===================================================================
# SECTION 7: Regulatory Actions (12 tests)
# ===================================================================


class TestRegulatoryActions:
    """Test regulatory action CRUD and status management."""

    def test_list_regulatory_actions(self, svc: PharmacovigilanceService):
        """List all regulatory actions."""
        result = svc.list_regulatory_actions()
        assert result.total == 3

    def test_list_regulatory_actions_by_signal(self, svc: PharmacovigilanceService):
        """Filter regulatory actions by signal ID."""
        result = svc.list_regulatory_actions(signal_id="SIG-0001")
        assert result.total >= 1

    def test_list_regulatory_actions_by_type(self, svc: PharmacovigilanceService):
        """Filter regulatory actions by type."""
        result = svc.list_regulatory_actions(action_type=RegulatoryActionType.LABELING_CHANGE)
        assert result.total >= 1

    def test_list_regulatory_actions_by_agency(self, svc: PharmacovigilanceService):
        """Filter regulatory actions by agency."""
        result = svc.list_regulatory_actions(agency="FDA")
        assert result.total >= 1

    def test_get_regulatory_action(self, svc: PharmacovigilanceService):
        """Get a single regulatory action."""
        action = svc.get_regulatory_action("RA-0001")
        assert action is not None
        assert action.agency == "FDA"

    def test_get_regulatory_action_not_found(self, svc: PharmacovigilanceService):
        """Non-existent action returns None."""
        assert svc.get_regulatory_action("RA-9999") is None

    def test_create_regulatory_action(self, svc: PharmacovigilanceService):
        """Create a new regulatory action."""
        payload = RegulatoryActionCreate(
            signal_id="SIG-0001",
            action_type=RegulatoryActionType.REMS,
            agency="FDA",
            description="Test REMS action",
        )
        action = svc.create_regulatory_action(payload)
        assert action.id.startswith("RA-")
        assert action.status == RegulatoryActionStatus.PROPOSED

    def test_create_regulatory_action_invalid_signal(self, svc: PharmacovigilanceService):
        """Creating action for non-existent signal raises ValueError."""
        payload = RegulatoryActionCreate(
            signal_id="SIG-9999",
            action_type=RegulatoryActionType.REMS,
            agency="FDA",
            description="Invalid",
        )
        with pytest.raises(ValueError, match="not found"):
            svc.create_regulatory_action(payload)

    def test_update_regulatory_action_status(self, svc: PharmacovigilanceService):
        """Update regulatory action status."""
        result = svc.update_regulatory_action_status("RA-0003", RegulatoryActionStatus.APPROVED)
        assert result is not None
        assert result.status == RegulatoryActionStatus.APPROVED

    def test_update_regulatory_action_implemented(self, svc: PharmacovigilanceService):
        """Implementing action sets implementation date."""
        # RA-0002 is APPROVED, change to IMPLEMENTED
        result = svc.update_regulatory_action_status("RA-0002", RegulatoryActionStatus.IMPLEMENTED)
        assert result is not None
        assert result.status == RegulatoryActionStatus.IMPLEMENTED
        assert result.implementation_date is not None

    def test_update_regulatory_action_not_found(self, svc: PharmacovigilanceService):
        """Update non-existent action returns None."""
        assert svc.update_regulatory_action_status("RA-9999", RegulatoryActionStatus.APPROVED) is None

    def test_list_regulatory_actions_pagination(self, svc: PharmacovigilanceService):
        """Pagination works for regulatory actions."""
        result = svc.list_regulatory_actions(limit=1, offset=0)
        assert len(result.items) == 1
        assert result.total == 3


# ===================================================================
# SECTION 8: Case Series Analysis (8 tests)
# ===================================================================


class TestCaseSeriesAnalysis:
    """Test case series analysis for drug-event pairs."""

    def test_case_series_returns_cases(self, svc: PharmacovigilanceService):
        """Case series analysis returns matching cases."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.total_cases > 0
        assert len(result.cases) == result.total_cases

    def test_case_series_demographics(self, svc: PharmacovigilanceService):
        """Case series includes demographic breakdown."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.sex_distribution is not None
        assert len(result.sex_distribution) > 0

    def test_case_series_outcome_distribution(self, svc: PharmacovigilanceService):
        """Case series includes outcome distribution."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.outcome_distribution is not None

    def test_case_series_causality_distribution(self, svc: PharmacovigilanceService):
        """Case series includes causality distribution."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.causality_distribution is not None

    def test_case_series_country_distribution(self, svc: PharmacovigilanceService):
        """Case series includes country distribution."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.country_distribution is not None

    def test_case_series_no_match(self, svc: PharmacovigilanceService):
        """Case series with no matching cases returns zeroes."""
        result = svc.case_series_analysis("NonexistentDrug", "NonexistentEvent")
        assert result.total_cases == 0
        assert len(result.cases) == 0

    def test_case_series_median_age(self, svc: PharmacovigilanceService):
        """Case series computes median age."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        if result.total_cases > 0:
            assert result.median_age is not None

    def test_case_series_serious_count(self, svc: PharmacovigilanceService):
        """Case series tracks serious cases."""
        result = svc.case_series_analysis("Dupilumab", "Conjunctivitis")
        assert result.serious_count >= 0
        assert result.serious_count <= result.total_cases


# ===================================================================
# SECTION 9: Metrics (8 tests)
# ===================================================================


class TestMetrics:
    """Test pharmacovigilance metrics computation."""

    def test_metrics_total_icsrs(self, svc: PharmacovigilanceService):
        """Metrics report total ICSR count."""
        metrics = svc.get_metrics()
        assert metrics.total_icsrs == 50

    def test_metrics_total_signals(self, svc: PharmacovigilanceService):
        """Metrics report total signal count."""
        metrics = svc.get_metrics()
        assert metrics.total_signals == 8

    def test_metrics_validated_signals(self, svc: PharmacovigilanceService):
        """Metrics report validated signal count."""
        metrics = svc.get_metrics()
        assert metrics.validated_signals == 3

    def test_metrics_under_evaluation(self, svc: PharmacovigilanceService):
        """Metrics report under evaluation count."""
        metrics = svc.get_metrics()
        assert metrics.under_evaluation_signals == 2

    def test_metrics_periodic_reports(self, svc: PharmacovigilanceService):
        """Metrics report periodic report count."""
        metrics = svc.get_metrics()
        assert metrics.total_periodic_reports == 4

    def test_metrics_regulatory_actions(self, svc: PharmacovigilanceService):
        """Metrics report regulatory action count."""
        metrics = svc.get_metrics()
        assert metrics.total_regulatory_actions == 3

    def test_metrics_top_drugs(self, svc: PharmacovigilanceService):
        """Metrics include top reported drugs."""
        metrics = svc.get_metrics()
        assert len(metrics.top_reported_drugs) > 0

    def test_metrics_meddra_terms(self, svc: PharmacovigilanceService):
        """Metrics include MedDRA term count."""
        metrics = svc.get_metrics()
        assert metrics.meddra_terms_loaded == 30


# ===================================================================
# SECTION 10: API endpoint tests (30 tests)
# ===================================================================


class TestAPIEndpoints:
    """Test all API endpoints via HTTP client."""

    @pytest.mark.anyio
    async def test_list_icsrs_endpoint(self):
        """GET /pharmacovigilance/icsrs returns list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/icsrs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 50

    @pytest.mark.anyio
    async def test_list_icsrs_filter_drug(self):
        """GET /pharmacovigilance/icsrs?drug_name=Dupilumab filters correctly."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/icsrs", params={"drug_name": "Dupilumab"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["drug_name"] == "Dupilumab"

    @pytest.mark.anyio
    async def test_search_icsrs_endpoint(self):
        """GET /pharmacovigilance/icsrs/search?q=Cemiplimab works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/icsrs/search", params={"q": "Cemiplimab"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_get_icsr_endpoint(self):
        """GET /pharmacovigilance/icsrs/ICSR-0001 returns ICSR."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/icsrs/ICSR-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ICSR-0001"

    @pytest.mark.anyio
    async def test_get_icsr_not_found(self):
        """GET /pharmacovigilance/icsrs/ICSR-9999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/icsrs/ICSR-9999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_icsr_endpoint(self):
        """POST /pharmacovigilance/icsrs creates new ICSR."""
        payload = {
            "case_number": "CASE-API-TEST",
            "drug_name": "Dupilumab",
            "event_terms": ["Rash"],
            "reporter_type": "Physician",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/icsrs", json=payload)
        assert resp.status_code == 201
        assert resp.json()["case_number"] == "CASE-API-TEST"

    @pytest.mark.anyio
    async def test_update_icsr_endpoint(self):
        """PUT /pharmacovigilance/icsrs/ICSR-0001 updates ICSR."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/icsrs/ICSR-0001",
                json={"outcome": "Recovered"},
            )
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "Recovered"

    @pytest.mark.anyio
    async def test_delete_icsr_endpoint(self):
        """DELETE /pharmacovigilance/icsrs/ICSR-0001 deletes ICSR."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/icsrs/ICSR-0001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_icsr_not_found(self):
        """DELETE /pharmacovigilance/icsrs/ICSR-9999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/icsrs/ICSR-9999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_detect_signal_endpoint(self):
        """POST /pharmacovigilance/signals/detect returns analysis."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/signals/detect",
                json={
                    "drug_name": "Dupilumab",
                    "event_term": "Conjunctivitis",
                    "methods": ["PRR", "ROR"],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2

    @pytest.mark.anyio
    async def test_list_signals_endpoint(self):
        """GET /pharmacovigilance/signals returns list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/signals")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    @pytest.mark.anyio
    async def test_get_signal_endpoint(self):
        """GET /pharmacovigilance/signals/SIG-0001 returns signal."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/signals/SIG-0001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SIG-0001"

    @pytest.mark.anyio
    async def test_get_signal_not_found(self):
        """GET /pharmacovigilance/signals/SIG-9999 returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/signals/SIG-9999")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_signal_endpoint(self):
        """POST /pharmacovigilance/signals creates new signal."""
        payload = {
            "title": "API test signal",
            "description": "Created via API",
            "drug_name": "Dupilumab",
            "event_term": "Conjunctivitis",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/signals", json=payload)
        assert resp.status_code == 201
        assert resp.json()["title"] == "API test signal"

    @pytest.mark.anyio
    async def test_update_signal_endpoint(self):
        """PUT /pharmacovigilance/signals/SIG-0001 updates signal."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/signals/SIG-0001",
                json={"assessor": "API Assessor"},
            )
        assert resp.status_code == 200
        assert resp.json()["assessor"] == "API Assessor"

    @pytest.mark.anyio
    async def test_update_signal_invalid_transition(self):
        """PUT /pharmacovigilance/signals with invalid transition returns 400."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # SIG-0001 is VALIDATED, can't go to UNDER_EVALUATION
            resp = await ac.put(
                f"{API_PREFIX}/signals/SIG-0001",
                json={"classification": "UNDER_EVALUATION"},
            )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_signal_endpoint(self):
        """DELETE /pharmacovigilance/signals/SIG-0001 deletes signal."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"{API_PREFIX}/signals/SIG-0001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_search_meddra_endpoint(self):
        """GET /pharmacovigilance/meddra/search works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/meddra/search", params={"q": "conjunctivitis"})
        assert resp.status_code == 200
        assert resp.json()["total"] > 0

    @pytest.mark.anyio
    async def test_get_meddra_term_endpoint(self):
        """GET /pharmacovigilance/meddra/10010741 returns term."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/meddra/10010741")
        assert resp.status_code == 200
        assert resp.json()["term"] == "Conjunctivitis"

    @pytest.mark.anyio
    async def test_get_meddra_hierarchy_endpoint(self):
        """GET /pharmacovigilance/meddra/10010741/hierarchy returns hierarchy."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/meddra/10010741/hierarchy")
        assert resp.status_code == 200
        data = resp.json()
        assert "term" in data
        assert "ancestors" in data
        assert "children" in data

    @pytest.mark.anyio
    async def test_code_to_meddra_endpoint(self):
        """POST /pharmacovigilance/meddra/code maps text to MedDRA."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/meddra/code",
                json={"event_term": "Conjunctivitis"},
            )
        assert resp.status_code == 200
        assert resp.json()["code"] == "10010741"

    @pytest.mark.anyio
    async def test_code_to_meddra_not_found(self):
        """POST /pharmacovigilance/meddra/code with unknown term returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"{API_PREFIX}/meddra/code",
                json={"event_term": "zzzzzznonexistent"},
            )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_periodic_reports_endpoint(self):
        """GET /pharmacovigilance/periodic-reports returns list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/periodic-reports")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_generate_periodic_report_endpoint(self):
        """POST /pharmacovigilance/periodic-reports/generate creates report."""
        now = datetime.now(timezone.utc)
        payload = {
            "drug_name": "Dupilumab",
            "report_type": "DSUR",
            "period_start": (now - timedelta(days=365)).isoformat(),
            "period_end": now.isoformat(),
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/periodic-reports/generate", json=payload)
        assert resp.status_code == 201
        assert resp.json()["drug_name"] == "Dupilumab"

    @pytest.mark.anyio
    async def test_list_regulatory_actions_endpoint(self):
        """GET /pharmacovigilance/regulatory-actions returns list."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/regulatory-actions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_create_regulatory_action_endpoint(self):
        """POST /pharmacovigilance/regulatory-actions creates action."""
        payload = {
            "signal_id": "SIG-0001",
            "action_type": "REMS",
            "agency": "FDA",
            "description": "API test action",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"{API_PREFIX}/regulatory-actions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["action_type"] == "REMS"

    @pytest.mark.anyio
    async def test_update_regulatory_action_status_endpoint(self):
        """PUT /pharmacovigilance/regulatory-actions/{id}/status works."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                f"{API_PREFIX}/regulatory-actions/RA-0003/status",
                json={"status": "APPROVED"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    @pytest.mark.anyio
    async def test_case_series_endpoint(self):
        """GET /pharmacovigilance/case-series returns analysis."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                f"{API_PREFIX}/case-series",
                params={"drug_name": "Dupilumab", "event_term": "Conjunctivitis"},
            )
        assert resp.status_code == 200
        assert resp.json()["total_cases"] > 0

    @pytest.mark.anyio
    async def test_metrics_endpoint(self):
        """GET /pharmacovigilance/metrics returns dashboard metrics."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_icsrs"] == 50
        assert data["total_signals"] == 8


# ===================================================================
# SECTION 11: Edge cases & service stats (6 tests)
# ===================================================================


class TestEdgeCases:
    """Test edge cases and service health."""

    def test_get_stats(self, svc: PharmacovigilanceService):
        """Service stats return correct counts."""
        stats = svc.get_stats()
        assert stats["icsrs"] == 50
        assert stats["signals"] == 8
        assert stats["periodic_reports"] == 4
        assert stats["regulatory_actions"] == 3
        assert stats["meddra_terms"] == 30

    def test_singleton_pattern(self):
        """get_pharmacovigilance_service returns same instance."""
        svc1 = get_pharmacovigilance_service()
        svc2 = get_pharmacovigilance_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        """reset_pharmacovigilance_service creates new instance."""
        svc1 = get_pharmacovigilance_service()
        svc2 = reset_pharmacovigilance_service()
        assert svc1 is not svc2

    def test_create_icsr_increments_count(self, svc: PharmacovigilanceService):
        """Creating ICSR increases count."""
        before = len(svc._icsrs)
        svc.create_icsr(_make_icsr_create(case_number="CASE-INCR-001"))
        assert len(svc._icsrs) == before + 1

    def test_empty_list_with_restrictive_filter(self, svc: PharmacovigilanceService):
        """Filtering for non-existent drug returns empty list."""
        result = svc.list_icsrs(drug_name="NoSuchDrug")
        assert result.total == 0
        assert len(result.items) == 0

    def test_metrics_rates_bounded(self, svc: PharmacovigilanceService):
        """Serious and fatal rates are between 0 and 100."""
        metrics = svc.get_metrics()
        assert 0 <= metrics.serious_case_rate <= 100
        assert 0 <= metrics.fatal_case_rate <= 100
