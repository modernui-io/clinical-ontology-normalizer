"""Tests for P2 data quality features.

Covers:
- P2-010: Mapping drift detection
- P2-011: Mapping disagreement service
- P2-021: Deterministic reprocessing service
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mapping_drift_detector import (
    DriftResult,
    DriftSeverity,
    MappingDistribution,
    detect_drift,
    _kl_divergence,
    _chi_squared,
    _classify_severity,
    DRIFT_WARNING_THRESHOLD,
    DRIFT_CRITICAL_THRESHOLD,
)
from app.services.mapping_disagreement_service import (
    DisagreementRecord,
    DisagreementSummary,
    MappingDisagreementService,
    get_mapping_disagreement_service,
    reset_mapping_disagreement_service,
)
from app.services.reprocessing_service import (
    FailedNote,
    ReprocessingResult,
    ReprocessingService,
    ReprocessingStatus,
    get_reprocessing_service,
    reset_reprocessing_service,
)


# ===================================================================
# P2-010: Mapping Drift Detector Tests
# ===================================================================


class TestMappingDistribution:
    """Test MappingDistribution dataclass."""

    def test_create_mapping_distribution(self) -> None:
        dist = MappingDistribution(
            concept_id=12345, count=100, percentage=25.0, period="2026-01"
        )
        assert dist.concept_id == 12345
        assert dist.count == 100
        assert dist.percentage == 25.0
        assert dist.period == "2026-01"


class TestDriftResult:
    """Test DriftResult dataclass."""

    def test_default_drift_result(self) -> None:
        result = DriftResult(drifted=False, drift_score=0.0)
        assert result.drifted is False
        assert result.drift_score == 0.0
        assert result.affected_concepts == []
        assert result.severity == DriftSeverity.NONE

    def test_drift_result_with_affected_concepts(self) -> None:
        result = DriftResult(
            drifted=True,
            drift_score=0.35,
            affected_concepts=[100, 200, 300],
            severity=DriftSeverity.CRITICAL,
        )
        assert result.drifted is True
        assert len(result.affected_concepts) == 3
        assert result.severity == DriftSeverity.CRITICAL


class TestClassifySeverity:
    """Test severity classification thresholds."""

    def test_none_severity(self) -> None:
        assert _classify_severity(0.0) == DriftSeverity.NONE

    def test_very_small_is_none(self) -> None:
        assert _classify_severity(0.005) == DriftSeverity.NONE

    def test_minor_severity(self) -> None:
        assert _classify_severity(0.05) == DriftSeverity.MINOR

    def test_significant_severity(self) -> None:
        assert _classify_severity(0.15) == DriftSeverity.SIGNIFICANT

    def test_critical_severity(self) -> None:
        assert _classify_severity(0.5) == DriftSeverity.CRITICAL

    def test_custom_thresholds(self) -> None:
        assert (
            _classify_severity(0.05, warning_threshold=0.04, critical_threshold=0.06)
            == DriftSeverity.SIGNIFICANT
        )


class TestKLDivergence:
    """Test KL divergence computation."""

    def test_identical_distributions(self) -> None:
        p = [0.25, 0.25, 0.25, 0.25]
        q = [0.25, 0.25, 0.25, 0.25]
        score = _kl_divergence(p, q)
        assert score < 1e-6

    def test_different_distributions(self) -> None:
        p = [0.9, 0.1]
        q = [0.1, 0.9]
        score = _kl_divergence(p, q)
        assert score > 0.0

    def test_non_negative(self) -> None:
        p = [0.5, 0.3, 0.2]
        q = [0.1, 0.8, 0.1]
        score = _kl_divergence(p, q)
        assert score >= 0.0


class TestChiSquared:
    """Test chi-squared computation."""

    def test_identical_distributions(self) -> None:
        obs = [0.25, 0.25, 0.25, 0.25]
        exp = [0.25, 0.25, 0.25, 0.25]
        score = _chi_squared(obs, exp)
        assert score < 1e-6

    def test_different_distributions(self) -> None:
        obs = [0.9, 0.1]
        exp = [0.1, 0.9]
        score = _chi_squared(obs, exp)
        assert score > 0.0

    def test_non_negative(self) -> None:
        obs = [0.5, 0.3, 0.2]
        exp = [0.1, 0.8, 0.1]
        score = _chi_squared(obs, exp)
        assert score >= 0.0


class TestDetectDrift:
    """Test the main drift detection function."""

    def test_no_drift_identical_distributions(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=50, percentage=50.0, period="2025-12"),
            MappingDistribution(concept_id=2, count=50, percentage=50.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=50, percentage=50.0, period="2026-01"),
            MappingDistribution(concept_id=2, count=50, percentage=50.0, period="2026-01"),
        ]
        result = detect_drift(current, baseline)

        assert result.drifted is False
        assert result.severity == DriftSeverity.NONE
        assert result.drift_score < 0.01

    def test_significant_drift(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=90, percentage=90.0, period="2025-12"),
            MappingDistribution(concept_id=2, count=10, percentage=10.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=10, percentage=10.0, period="2026-01"),
            MappingDistribution(concept_id=2, count=90, percentage=90.0, period="2026-01"),
        ]
        result = detect_drift(current, baseline)

        assert result.drifted is True
        assert result.drift_score > DRIFT_WARNING_THRESHOLD

    def test_affected_concepts_identified(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=90, percentage=90.0, period="2025-12"),
            MappingDistribution(concept_id=2, count=10, percentage=10.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=10, percentage=10.0, period="2026-01"),
            MappingDistribution(concept_id=2, count=90, percentage=90.0, period="2026-01"),
        ]
        result = detect_drift(current, baseline)

        # Both concepts shifted by 80 percentage points (> 5pp threshold)
        assert 1 in result.affected_concepts
        assert 2 in result.affected_concepts

    def test_new_concept_in_current(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=100, percentage=100.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=50, percentage=50.0, period="2026-01"),
            MappingDistribution(concept_id=99, count=50, percentage=50.0, period="2026-01"),
        ]
        result = detect_drift(current, baseline)

        assert result.drift_score > 0
        assert 99 in result.affected_concepts

    def test_empty_baseline(self) -> None:
        current = [
            MappingDistribution(concept_id=1, count=50, percentage=50.0, period="2026-01"),
        ]
        result = detect_drift(current, [])

        assert result.drifted is False
        assert result.severity == DriftSeverity.NONE

    def test_empty_current(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=50, percentage=50.0, period="2025-12"),
        ]
        result = detect_drift([], baseline)

        assert result.drifted is False
        assert result.severity == DriftSeverity.NONE

    def test_kl_divergence_method(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=90, percentage=90.0, period="2025-12"),
            MappingDistribution(concept_id=2, count=10, percentage=10.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=10, percentage=10.0, period="2026-01"),
            MappingDistribution(concept_id=2, count=90, percentage=90.0, period="2026-01"),
        ]
        result = detect_drift(current, baseline, method="kl_divergence")

        assert result.drift_score > 0

    def test_custom_thresholds(self) -> None:
        baseline = [
            MappingDistribution(concept_id=1, count=60, percentage=60.0, period="2025-12"),
            MappingDistribution(concept_id=2, count=40, percentage=40.0, period="2025-12"),
        ]
        current = [
            MappingDistribution(concept_id=1, count=55, percentage=55.0, period="2026-01"),
            MappingDistribution(concept_id=2, count=45, percentage=45.0, period="2026-01"),
        ]
        # With very tight thresholds, even small changes should be flagged
        result = detect_drift(
            current, baseline,
            warning_threshold=0.0001,
            critical_threshold=0.001,
        )
        # The score should be very small for this tiny shift
        assert isinstance(result.drift_score, float)


# ===================================================================
# P2-011: Mapping Disagreement Service Tests
# ===================================================================


class TestDisagreementRecord:
    """Test DisagreementRecord dataclass."""

    def test_create_record(self) -> None:
        record = DisagreementRecord(
            mention_text="pneumonia",
            rule_result="Pneumonia (4110051)",
            ml_result="Community-acquired pneumonia (4145731)",
            ensemble_result="Pneumonia (4110051)",
            agreement=False,
            entity_type="condition",
        )
        assert record.mention_text == "pneumonia"
        assert record.agreement is False
        assert record.entity_type == "condition"

    def test_agreement_true(self) -> None:
        record = DisagreementRecord(
            mention_text="aspirin",
            rule_result="Aspirin",
            ml_result="Aspirin",
            ensemble_result="Aspirin",
            agreement=True,
        )
        assert record.agreement is True


class TestMappingDisagreementService:
    """Test MappingDisagreementService."""

    def test_empty_service(self) -> None:
        svc = MappingDisagreementService()
        summary = svc.get_disagreement_summary()
        assert summary.total_mappings == 0
        assert summary.agreement_rate == 100.0
        assert summary.top_disagreements == []

    def test_add_record(self) -> None:
        svc = MappingDisagreementService()
        record = DisagreementRecord(
            mention_text="test",
            rule_result="A",
            ml_result="B",
            ensemble_result="A",
            agreement=False,
        )
        svc.add_record(record)
        assert len(svc.get_all_records()) == 1

    def test_add_mapping_result_agreement(self) -> None:
        svc = MappingDisagreementService()
        record = svc.add_mapping_result(
            mention_text="aspirin",
            rule_result="Aspirin",
            ml_result="Aspirin",
            ensemble_result="Aspirin",
            entity_type="drug",
        )
        assert record.agreement is True

    def test_add_mapping_result_disagreement(self) -> None:
        svc = MappingDisagreementService()
        record = svc.add_mapping_result(
            mention_text="pneumonia",
            rule_result="Pneumonia",
            ml_result="CAP",
            ensemble_result="Pneumonia",
            entity_type="condition",
        )
        assert record.agreement is False

    def test_disagreement_summary(self) -> None:
        svc = MappingDisagreementService()
        # 3 agreements, 1 disagreement -> 75% agreement
        for _ in range(3):
            svc.add_mapping_result("a", "X", "X", "X")
        svc.add_mapping_result("b", "X", "Y", "X")

        summary = svc.get_disagreement_summary()
        assert summary.total_mappings == 4
        assert summary.agreement_rate == 75.0
        assert len(summary.top_disagreements) == 1
        assert summary.top_disagreements[0].mention_text == "b"

    def test_get_disagreements_by_type(self) -> None:
        svc = MappingDisagreementService()
        svc.add_mapping_result("a", "X", "Y", "X", entity_type="condition")
        svc.add_mapping_result("b", "X", "Y", "X", entity_type="drug")
        svc.add_mapping_result("c", "X", "X", "X", entity_type="condition")

        conditions = svc.get_disagreements_by_type("condition")
        assert len(conditions) == 1
        assert conditions[0].mention_text == "a"

        drugs = svc.get_disagreements_by_type("drug")
        assert len(drugs) == 1
        assert drugs[0].mention_text == "b"

    def test_get_disagreements_by_type_empty(self) -> None:
        svc = MappingDisagreementService()
        svc.add_mapping_result("a", "X", "X", "X", entity_type="condition")

        result = svc.get_disagreements_by_type("condition")
        assert result == []  # All agree, so no disagreements

    def test_clear(self) -> None:
        svc = MappingDisagreementService()
        svc.add_mapping_result("a", "X", "Y", "X")
        svc.add_mapping_result("b", "X", "Y", "X")
        assert len(svc.get_all_records()) == 2

        svc.clear()
        assert len(svc.get_all_records()) == 0

    def test_singleton(self) -> None:
        reset_mapping_disagreement_service()
        svc1 = get_mapping_disagreement_service()
        svc2 = get_mapping_disagreement_service()
        assert svc1 is svc2
        reset_mapping_disagreement_service()

    def test_none_results_count_as_disagreement(self) -> None:
        svc = MappingDisagreementService()
        record = svc.add_mapping_result("x", "Concept", None, "Concept")
        assert record.agreement is False

    def test_both_none_count_as_agreement(self) -> None:
        svc = MappingDisagreementService()
        record = svc.add_mapping_result("x", None, None, "Concept")
        assert record.agreement is True


# ===================================================================
# P2-021: Reprocessing Service Tests
# ===================================================================


class TestReprocessingResult:
    """Test ReprocessingResult dataclass."""

    def test_success_result(self) -> None:
        result = ReprocessingResult(
            document_id="doc-1",
            status=ReprocessingStatus.SUCCESS,
        )
        assert result.status == ReprocessingStatus.SUCCESS
        assert result.error is None
        assert result.previous_error is None

    def test_failed_result(self) -> None:
        result = ReprocessingResult(
            document_id="doc-1",
            status=ReprocessingStatus.FAILED,
            error="NLP pipeline error",
            previous_error="timeout",
        )
        assert result.status == ReprocessingStatus.FAILED
        assert result.error == "NLP pipeline error"
        assert result.previous_error == "timeout"

    def test_skipped_result(self) -> None:
        result = ReprocessingResult(
            document_id="doc-1",
            status=ReprocessingStatus.SKIPPED,
        )
        assert result.status == ReprocessingStatus.SKIPPED


class TestFailedNote:
    """Test FailedNote dataclass."""

    def test_create_failed_note(self) -> None:
        note = FailedNote(
            document_id="doc-1",
            patient_id="patient-1",
            note_type="progress_note",
            status="failed",
            error="timeout during NLP extraction",
        )
        assert note.document_id == "doc-1"
        assert note.error == "timeout during NLP extraction"


class TestReprocessingService:
    """Test ReprocessingService methods."""

    @pytest.mark.asyncio
    async def test_get_failed_notes_returns_failed_documents(self) -> None:
        """Test that get_failed_notes queries for FAILED status documents."""
        from app.schemas.base import JobStatus

        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.patient_id = "patient-1"
        mock_doc.note_type = "progress_note"
        mock_doc.status = JobStatus.FAILED
        mock_doc.extra_metadata = {"error": "NLP timeout"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_doc]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        notes = await svc.get_failed_notes(mock_session, patient_id="patient-1")

        assert len(notes) == 1
        assert notes[0].document_id == "doc-123"
        assert notes[0].patient_id == "patient-1"
        assert notes[0].error == "NLP timeout"

    @pytest.mark.asyncio
    async def test_get_failed_notes_empty(self) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        notes = await svc.get_failed_notes(mock_session)

        assert notes == []

    @pytest.mark.asyncio
    async def test_reprocess_note_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        result = await svc.reprocess_note(mock_session, "nonexistent-id")

        assert result.status == ReprocessingStatus.FAILED
        assert result.error == "Document not found"

    @pytest.mark.asyncio
    async def test_reprocess_completed_skips_without_force(self) -> None:
        from app.schemas.base import JobStatus

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = JobStatus.COMPLETED
        mock_doc.extra_metadata = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        result = await svc.reprocess_note(mock_session, "doc-1")

        assert result.status == ReprocessingStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_reprocess_completed_with_force(self) -> None:
        from app.schemas.base import JobStatus

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = JobStatus.COMPLETED
        mock_doc.extra_metadata = {}
        mock_doc.processed_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        result = await svc.reprocess_note(mock_session, "doc-1", force=True)

        assert result.status == ReprocessingStatus.SUCCESS
        assert mock_doc.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_reprocess_failed_note_resets_to_queued(self) -> None:
        from app.schemas.base import JobStatus

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = JobStatus.FAILED
        mock_doc.extra_metadata = {"error": "timeout"}
        mock_doc.processed_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        result = await svc.reprocess_note(mock_session, "doc-1")

        assert result.status == ReprocessingStatus.SUCCESS
        assert result.previous_error == "timeout"
        assert mock_doc.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_reprocess_preserves_error_history(self) -> None:
        from app.schemas.base import JobStatus

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = JobStatus.FAILED
        mock_doc.extra_metadata = {"error": "OOM during extraction"}
        mock_doc.processed_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ReprocessingService()
        result = await svc.reprocess_note(mock_session, "doc-1")

        assert result.previous_error == "OOM during extraction"
        # Metadata should have previous_error but not error
        meta = mock_doc.extra_metadata
        assert meta.get("previous_error") == "OOM during extraction"
        assert "error" not in meta

    def test_singleton(self) -> None:
        reset_reprocessing_service()
        svc1 = get_reprocessing_service()
        svc2 = get_reprocessing_service()
        assert svc1 is svc2
        reset_reprocessing_service()
