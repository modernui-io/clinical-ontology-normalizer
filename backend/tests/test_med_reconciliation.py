"""Tests for Medication Reconciliation Service.

Tests verify:
- Matching medications are identified
- New medications flagged correctly
- Discontinued medications detected
- Dose changes identified with severity
- Duplicate detection
- Contraindication flagging (high-risk drug classes)
"""

import pytest

from app.services.med_reconciliation_service import (
    DiscrepancyType,
    MedReconciliationService,
    Severity,
    reset_med_reconciliation_service,
)


@pytest.fixture(autouse=True)
def reset():
    reset_med_reconciliation_service()
    yield
    reset_med_reconciliation_service()


@pytest.fixture
def service():
    return MedReconciliationService()


def med(name, dose="", frequency="", route="", drug_class="", rxnorm_code=""):
    return {
        "name": name,
        "dose": dose,
        "frequency": frequency,
        "route": route,
        "drug_class": drug_class,
        "rxnorm_code": rxnorm_code,
    }


class TestMedicationMatching:
    """Test matching medications are identified."""

    def test_exact_name_match(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", dose="10mg")],
            target_meds=[med("Lisinopril", dose="10mg")],
        )
        assert len(result.matched) == 1
        assert result.discrepancies == []

    def test_case_insensitive_match(self, service):
        result = service.reconcile(
            source_meds=[med("lisinopril", dose="10mg")],
            target_meds=[med("Lisinopril", dose="10mg")],
        )
        assert len(result.matched) == 1

    def test_rxnorm_code_match(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", rxnorm_code="104377")],
            target_meds=[med("Zestril", rxnorm_code="104377")],
        )
        assert len(result.matched) == 1

    def test_no_match_different_names(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril")],
            target_meds=[med("Metformin")],
        )
        assert len(result.matched) == 0

    def test_multiple_matches(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril"), med("Metformin"), med("Atorvastatin")],
            target_meds=[med("Metformin"), med("Lisinopril"), med("Atorvastatin")],
        )
        assert len(result.matched) == 3

    def test_counts_are_correct(self, service):
        result = service.reconcile(
            source_meds=[med("A"), med("B")],
            target_meds=[med("B"), med("C"), med("D")],
        )
        assert result.source_count == 2
        assert result.target_count == 3


class TestNewMedications:
    """Test new medications flagged correctly."""

    def test_new_medication_detected(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril")],
            target_meds=[med("Lisinopril"), med("Metformin")],
        )
        new_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.NEW]
        assert len(new_discs) == 1
        assert new_discs[0].medication_name == "Metformin"

    def test_multiple_new_medications(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Metformin"), med("Atorvastatin")],
        )
        new_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.NEW]
        assert len(new_discs) == 2

    def test_new_medication_details(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Metformin")],
            target_label="discharge",
        )
        new_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.NEW]
        assert "discharge" in new_discs[0].details

    def test_new_high_risk_med_high_severity(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Warfarin", drug_class="anticoagulant")],
        )
        new_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.NEW]
        assert new_discs[0].severity == Severity.HIGH


class TestDiscontinuedMedications:
    """Test discontinued medications detected."""

    def test_discontinued_medication_detected(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril"), med("Metformin")],
            target_meds=[med("Lisinopril")],
        )
        disc = [d for d in result.discrepancies if d.type == DiscrepancyType.DISCONTINUED]
        assert len(disc) == 1
        assert disc[0].medication_name == "Metformin"

    def test_all_discontinued(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril"), med("Metformin")],
            target_meds=[],
        )
        disc = [d for d in result.discrepancies if d.type == DiscrepancyType.DISCONTINUED]
        assert len(disc) == 2

    def test_discontinued_details_include_labels(self, service):
        result = service.reconcile(
            source_meds=[med("Metformin")],
            target_meds=[],
            source_label="admission",
            target_label="discharge",
        )
        disc = [d for d in result.discrepancies if d.type == DiscrepancyType.DISCONTINUED]
        assert "admission" in disc[0].details
        assert "discharge" in disc[0].details

    def test_discontinued_high_risk_med_high_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Heparin", drug_class="anticoagulant")],
            target_meds=[],
        )
        disc = [d for d in result.discrepancies if d.type == DiscrepancyType.DISCONTINUED]
        assert disc[0].severity == Severity.HIGH


class TestDoseChanges:
    """Test dose changes identified with severity."""

    def test_dose_change_detected(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", dose="10mg")],
            target_meds=[med("Lisinopril", dose="20mg")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert len(dose_discs) == 1
        assert "10mg" in dose_discs[0].details
        assert "20mg" in dose_discs[0].details

    def test_dose_change_medium_severity_default(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", dose="10mg", drug_class="ace_inhibitor")],
            target_meds=[med("Lisinopril", dose="20mg", drug_class="ace_inhibitor")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert dose_discs[0].severity == Severity.MEDIUM

    def test_dose_change_high_risk_class_high_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Warfarin", dose="5mg", drug_class="anticoagulant")],
            target_meds=[med("Warfarin", dose="10mg", drug_class="anticoagulant")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert dose_discs[0].severity == Severity.HIGH

    def test_dose_change_low_risk_class_low_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Vitamin D", dose="1000IU", drug_class="vitamin")],
            target_meds=[med("Vitamin D", dose="2000IU", drug_class="vitamin")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert dose_discs[0].severity == Severity.LOW

    def test_no_dose_change_when_doses_match(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", dose="10mg")],
            target_meds=[med("Lisinopril", dose="10mg")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert len(dose_discs) == 0

    def test_no_dose_change_when_dose_empty(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", dose="")],
            target_meds=[med("Lisinopril", dose="20mg")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert len(dose_discs) == 0


class TestFrequencyChanges:
    """Test frequency changes detected."""

    def test_frequency_change_detected(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", frequency="QD")],
            target_meds=[med("Lisinopril", frequency="BID")],
        )
        freq_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.FREQUENCY_CHANGE]
        assert len(freq_discs) == 1
        assert "QD" in freq_discs[0].details
        assert "BID" in freq_discs[0].details

    def test_no_frequency_change_when_empty(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril", frequency="")],
            target_meds=[med("Lisinopril", frequency="BID")],
        )
        freq_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.FREQUENCY_CHANGE]
        assert len(freq_discs) == 0


class TestDuplicateDetection:
    """Test duplicate detection."""

    def test_duplicate_in_target_detected(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril")],
            target_meds=[med("Lisinopril"), med("Lisinopril")],
        )
        dup_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DUPLICATE]
        assert len(dup_discs) == 1

    def test_duplicate_case_insensitive(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Lisinopril"), med("lisinopril")],
        )
        dup_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DUPLICATE]
        assert len(dup_discs) == 1

    def test_duplicate_severity_medium(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Lisinopril"), med("Lisinopril")],
        )
        dup_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DUPLICATE]
        assert dup_discs[0].severity == Severity.MEDIUM

    def test_no_duplicate_different_names(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Lisinopril"), med("Metformin")],
        )
        dup_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DUPLICATE]
        assert len(dup_discs) == 0


class TestContraindications:
    """Test contraindication flagging (high-risk drug classes)."""

    def test_anticoagulant_new_is_high_severity(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Warfarin", drug_class="anticoagulant")],
        )
        assert any(
            d.severity == Severity.HIGH and d.medication_name == "Warfarin"
            for d in result.discrepancies
        )

    def test_insulin_discontinued_is_high_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Insulin Glargine", drug_class="insulin")],
            target_meds=[],
        )
        disc = [d for d in result.discrepancies if d.type == DiscrepancyType.DISCONTINUED]
        assert disc[0].severity == Severity.HIGH

    def test_opioid_dose_change_is_high_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Morphine", dose="15mg", drug_class="opioid")],
            target_meds=[med("Morphine", dose="30mg", drug_class="opioid")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert dose_discs[0].severity == Severity.HIGH

    def test_immunosuppressant_is_high_severity(self, service):
        result = service.reconcile(
            source_meds=[med("Tacrolimus", dose="2mg", drug_class="immunosuppressant")],
            target_meds=[med("Tacrolimus", dose="4mg", drug_class="immunosuppressant")],
        )
        dose_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.DOSE_CHANGE]
        assert dose_discs[0].severity == Severity.HIGH

    def test_supplement_is_low_severity(self, service):
        result = service.reconcile(
            source_meds=[],
            target_meds=[med("Fish Oil", drug_class="supplement")],
        )
        new_discs = [d for d in result.discrepancies if d.type == DiscrepancyType.NEW]
        assert new_discs[0].severity == Severity.LOW


class TestResultRetrieval:
    """Test result storage and retrieval."""

    def test_result_has_id(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril")],
            target_meds=[med("Lisinopril")],
        )
        assert result.id is not None
        assert len(result.id) > 0

    def test_get_result_by_id(self, service):
        result = service.reconcile(
            source_meds=[med("Lisinopril")],
            target_meds=[med("Metformin")],
        )
        retrieved = service.get_result(result.id)
        assert retrieved is not None
        assert retrieved.id == result.id

    def test_get_nonexistent_result(self, service):
        result = service.get_result("nonexistent-id")
        assert result is None

    def test_result_preserves_labels(self, service):
        result = service.reconcile(
            source_meds=[med("A")],
            target_meds=[med("B")],
            source_label="EHR",
            target_label="patient-reported",
        )
        assert result.source_label == "EHR"
        assert result.target_label == "patient-reported"
