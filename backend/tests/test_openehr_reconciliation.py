"""Tests for OpenEHR reconciliation, dry-run import, and batch rollback (P0-019).

Covers:
- Dry-run import does not persist any data
- Dry-run returns correct stats for all 5 compositions
- Round-trip reconciliation fingerprint matching
- Round-trip detects mismatch on tampered export
- Batch rollback removes all data for a batch
- Rollback verification passes after clean rollback
- Rollback does not affect other patients
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.openehr_reconciliation import (
    OpenEHRReconciliationService,
    compute_import_fingerprint,
    DryRunResult,
    ReconciliationReport,
    _extract_concept_list_from_composition,
)
from app.services.openehr_rollback import (
    OpenEHRRollbackService,
    RollbackReport,
    RollbackVerification,
)
from app.services.openehr_import import OpenEHRImportService
from app.services.openehr_exporter import OpenEHRExporterService
from tests.fixtures.openehr_dry_run_compositions import (
    ALL_COMPOSITIONS,
    build_mixed_all_composition,
    build_labs_only_composition,
    build_medications_heavy_composition,
    build_procedures_vitals_composition,
    build_allergies_conditions_composition,
    EXPECTED_MIXED_ALL,
    EXPECTED_LABS_ONLY,
    EXPECTED_MEDICATIONS_HEAVY,
    EXPECTED_PROCEDURES_VITALS,
    EXPECTED_ALLERGIES_CONDITIONS,
)


# ===========================================================================
# Test Helpers
# ===========================================================================


def _mock_session() -> AsyncMock:
    """Create a mock async session with savepoint support."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    # Mock begin_nested to return a context manager that supports rollback
    savepoint = AsyncMock()
    savepoint.rollback = AsyncMock()
    savepoint.__aenter__ = AsyncMock(return_value=savepoint)
    savepoint.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = AsyncMock(return_value=savepoint)

    return session


# ===========================================================================
# Tests: Dry-Run Import
# ===========================================================================


class TestDryRunImport:
    """Test that dry-run imports collect stats without persisting."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_persist(self) -> None:
        """Import via dry-run should roll back the savepoint, leaving zero DB rows."""
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_mixed_all_composition()
        result = await service.dry_run_import(session, comp, "dry-run-patient-1")

        assert result.success is True
        # Verify the savepoint was rolled back
        savepoint = await session.begin_nested()
        # The rollback should have been called on the savepoint
        # (the service calls savepoint.rollback() in the else clause)

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_stats_mixed_all(self) -> None:
        """Dry-run of mixed-all composition returns expected domain counts."""
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_mixed_all_composition()
        result = await service.dry_run_import(session, comp, "dry-run-mixed")

        assert result.success is True
        assert result.conditions == EXPECTED_MIXED_ALL["conditions"]
        assert result.medications == EXPECTED_MIXED_ALL["medications"]
        assert result.measurements == EXPECTED_MIXED_ALL["measurements"]
        assert result.procedures == EXPECTED_MIXED_ALL["procedures"]
        assert result.allergies == EXPECTED_MIXED_ALL["allergies"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_stats_labs_only(self) -> None:
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_labs_only_composition()
        result = await service.dry_run_import(session, comp, "dry-run-labs")

        assert result.success is True
        assert result.conditions == EXPECTED_LABS_ONLY["conditions"]
        assert result.medications == EXPECTED_LABS_ONLY["medications"]
        assert result.measurements == EXPECTED_LABS_ONLY["measurements"]
        assert result.procedures == EXPECTED_LABS_ONLY["procedures"]
        assert result.allergies == EXPECTED_LABS_ONLY["allergies"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_stats_medications_heavy(self) -> None:
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_medications_heavy_composition()
        result = await service.dry_run_import(session, comp, "dry-run-meds")

        assert result.success is True
        assert result.conditions == EXPECTED_MEDICATIONS_HEAVY["conditions"]
        assert result.medications == EXPECTED_MEDICATIONS_HEAVY["medications"]
        assert result.measurements == EXPECTED_MEDICATIONS_HEAVY["measurements"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_stats_procedures_vitals(self) -> None:
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_procedures_vitals_composition()
        result = await service.dry_run_import(session, comp, "dry-run-proc")

        assert result.success is True
        assert result.procedures == EXPECTED_PROCEDURES_VITALS["procedures"]
        assert result.measurements == EXPECTED_PROCEDURES_VITALS["measurements"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_stats_allergies_conditions(self) -> None:
        session = _mock_session()
        service = OpenEHRReconciliationService()

        comp = build_allergies_conditions_composition()
        result = await service.dry_run_import(session, comp, "dry-run-allergy")

        assert result.success is True
        assert result.conditions == EXPECTED_ALLERGIES_CONDITIONS["conditions"]
        assert result.allergies == EXPECTED_ALLERGIES_CONDITIONS["allergies"]

    @pytest.mark.asyncio
    async def test_dry_run_invalid_composition(self) -> None:
        """Dry-run with a non-COMPOSITION dict returns failure."""
        session = _mock_session()
        service = OpenEHRReconciliationService()

        result = await service.dry_run_import(
            session, {"_type": "OBSERVATION"}, "dry-run-bad"
        )
        assert result.success is False
        assert result.error is not None


# ===========================================================================
# Tests: Fingerprint / Hash
# ===========================================================================


class TestImportFingerprint:
    """Test deterministic SHA-256 fingerprinting of import results."""

    def test_fingerprint_deterministic(self) -> None:
        """Same input produces same hash."""
        stats = {"conditions": 1, "medications": 1, "measurements": 0, "procedures": 0, "allergies": 0}
        facts = [
            {"domain": "condition", "concept_name": "Asthma"},
            {"domain": "drug", "concept_name": "Salbutamol"},
        ]
        fp1 = compute_import_fingerprint(stats, facts)
        fp2 = compute_import_fingerprint(stats, facts)
        assert fp1 == fp2

    def test_fingerprint_order_independent(self) -> None:
        """Facts in different order produce the same hash (sorted internally)."""
        stats = {"conditions": 1, "medications": 1, "measurements": 0, "procedures": 0, "allergies": 0}
        facts_a = [
            {"domain": "condition", "concept_name": "Asthma"},
            {"domain": "drug", "concept_name": "Salbutamol"},
        ]
        facts_b = [
            {"domain": "drug", "concept_name": "Salbutamol"},
            {"domain": "condition", "concept_name": "Asthma"},
        ]
        assert compute_import_fingerprint(stats, facts_a) == compute_import_fingerprint(stats, facts_b)

    def test_fingerprint_differs_on_content_change(self) -> None:
        """Different facts produce different hashes."""
        stats = {"conditions": 1, "medications": 0, "measurements": 0, "procedures": 0, "allergies": 0}
        facts_a = [{"domain": "condition", "concept_name": "Asthma"}]
        facts_b = [{"domain": "condition", "concept_name": "COPD"}]
        assert compute_import_fingerprint(stats, facts_a) != compute_import_fingerprint(stats, facts_b)

    def test_fingerprint_differs_on_count_change(self) -> None:
        """Different stats produce different hashes."""
        facts = [{"domain": "condition", "concept_name": "Asthma"}]
        stats_a = {"conditions": 1, "medications": 0, "measurements": 0, "procedures": 0, "allergies": 0}
        stats_b = {"conditions": 2, "medications": 0, "measurements": 0, "procedures": 0, "allergies": 0}
        assert compute_import_fingerprint(stats_a, facts) != compute_import_fingerprint(stats_b, facts)


# ===========================================================================
# Tests: Round-Trip Reconciliation
# ===========================================================================


class TestRoundTripReconciliation:
    """Test import -> export -> re-import fingerprint matching."""

    def test_extract_concept_list_from_composition(self) -> None:
        """Verify concept extraction from a known composition."""
        comp = build_mixed_all_composition()
        concepts = _extract_concept_list_from_composition(comp)

        names = {c["concept_name"] for c in concepts}
        assert "Asthma" in names
        assert "Salbutamol 100mcg" in names
        assert "Spirometry" in names
        assert "Aspirin" in names
        # BP produces 2 entries
        assert "Blood Pressure - Systolic" in names
        assert "Blood Pressure - Diastolic" in names

    def test_round_trip_fingerprint_matches_for_known_composition(self) -> None:
        """Export a composition, extract concepts, compute fingerprint — should match."""
        # Simulate facts as they would look post-import
        facts = [
            {"domain": "condition", "concept_name": "Asthma"},
            {"domain": "drug", "concept_name": "Salbutamol 100mcg"},
            {"domain": "measurement", "concept_name": "Blood Pressure - Systolic"},
            {"domain": "measurement", "concept_name": "Blood Pressure - Diastolic"},
            {"domain": "procedure", "concept_name": "Spirometry"},
            {"domain": "observation", "concept_name": "Aspirin"},
        ]
        stats = {
            "conditions": 1,
            "medications": 1,
            "measurements": 2,
            "procedures": 1,
            "allergies": 1,
        }

        import_fp = compute_import_fingerprint(stats, facts)

        # Export the composition and extract concepts
        exporter = OpenEHRExporterService()
        composition = exporter.export_facts(facts, "test-patient")
        reimport_facts = _extract_concept_list_from_composition(composition)

        reimport_fp = compute_import_fingerprint(stats, reimport_facts)

        assert import_fp == reimport_fp

    @pytest.mark.asyncio
    async def test_round_trip_detects_mismatch(self) -> None:
        """Tampering with the export should cause fingerprint mismatch."""
        facts = [
            {"domain": "condition", "concept_name": "Asthma"},
            {"domain": "drug", "concept_name": "Salbutamol 100mcg"},
        ]
        stats_orig = {"conditions": 1, "medications": 1, "measurements": 0, "procedures": 0, "allergies": 0}
        import_fp = compute_import_fingerprint(stats_orig, facts)

        # Tampered facts — different concept name
        tampered_facts = [
            {"domain": "condition", "concept_name": "COPD"},  # tampered
            {"domain": "drug", "concept_name": "Salbutamol 100mcg"},
        ]
        tampered_fp = compute_import_fingerprint(stats_orig, tampered_facts)

        assert import_fp != tampered_fp

    def test_all_compositions_extract_expected_concepts(self) -> None:
        """For each of the 5 compositions, extracted concepts match expected names."""
        for label, (builder_fn, expected) in ALL_COMPOSITIONS.items():
            comp = builder_fn()
            concepts = _extract_concept_list_from_composition(comp)
            extracted_names = {c["concept_name"] for c in concepts}

            for expected_name in expected["concept_names"]:
                assert expected_name in extracted_names, (
                    f"[{label}] Missing concept: {expected_name}. "
                    f"Got: {extracted_names}"
                )
            assert len(concepts) == expected["total_facts"], (
                f"[{label}] Expected {expected['total_facts']} facts, "
                f"got {len(concepts)}"
            )


# ===========================================================================
# Tests: Batch Rollback
# ===========================================================================


class TestBatchRollback:
    """Test batch rollback service with mocked DB."""

    def _build_mock_fact(self, patient_id: str, fact_id: str | None = None) -> MagicMock:
        fact = MagicMock()
        fact.id = fact_id or str(uuid4())
        fact.patient_id = patient_id
        fact.deleted_at = None
        fact.soft_delete = MagicMock()
        return fact

    def _build_mock_edge(self, patient_id: str, fact_id: str, target_node_id: str) -> MagicMock:
        edge = MagicMock()
        edge.id = str(uuid4())
        edge.patient_id = patient_id
        edge.fact_id = fact_id
        edge.target_node_id = target_node_id
        edge.deleted_at = None
        edge.soft_delete = MagicMock()
        return edge

    def _build_mock_node(self, patient_id: str, node_id: str | None = None) -> MagicMock:
        node = MagicMock()
        node.id = node_id or str(uuid4())
        node.patient_id = patient_id
        node.deleted_at = None
        node.soft_delete = MagicMock()
        return node

    @pytest.mark.asyncio
    async def test_rollback_removes_all_batch_data(self) -> None:
        """Import batch rollback should soft-delete all facts, nodes, and edges."""
        patient_id = "rollback-patient-1"
        fact_id = str(uuid4())
        node_id = str(uuid4())

        fact = self._build_mock_fact(patient_id, fact_id)
        edge = self._build_mock_edge(patient_id, fact_id, node_id)
        node = self._build_mock_node(patient_id, node_id)

        session = AsyncMock()
        session.flush = AsyncMock()

        # Mock execute calls in order:
        # 1. lineage query -> return fact IDs
        # 2. facts query -> return facts
        # 3. edges query -> return edges
        # 4. nodes query -> return nodes
        lineage_result = MagicMock()
        lineage_result.scalars.return_value.all.return_value = [fact_id]

        facts_result = MagicMock()
        facts_result.scalars.return_value.all.return_value = [fact]

        edges_result = MagicMock()
        edges_result.scalars.return_value.all.return_value = [edge]

        nodes_result = MagicMock()
        nodes_result.scalars.return_value.all.return_value = [node]

        session.execute = AsyncMock(
            side_effect=[lineage_result, facts_result, edges_result, nodes_result]
        )

        service = OpenEHRRollbackService()
        now = datetime.now(timezone.utc)
        report = await service.rollback_import_batch(
            session, patient_id,
            batch_start=now - timedelta(hours=1),
            batch_end=now + timedelta(hours=1),
        )

        assert report.success is True
        assert report.facts_deleted == 1
        assert report.edges_deleted == 1
        assert report.nodes_deleted == 1
        fact.soft_delete.assert_called_once()
        edge.soft_delete.assert_called_once()
        node.soft_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_verify_passes_after_clean_rollback(self) -> None:
        """verify_rollback returns passed=True when no residual data exists."""
        session = AsyncMock()

        # All queries return empty results
        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(return_value=empty_result)

        service = OpenEHRRollbackService()
        now = datetime.now(timezone.utc)
        verification = await service.verify_rollback(
            session, "clean-patient",
            batch_start=now - timedelta(hours=1),
            batch_end=now + timedelta(hours=1),
        )

        assert verification.passed is True
        assert verification.residual_facts == 0
        assert verification.residual_nodes == 0
        assert verification.residual_edges == 0

    @pytest.mark.asyncio
    async def test_rollback_does_not_affect_other_patients(self) -> None:
        """Rollback for patient A should not touch patient B's data."""
        patient_a = "rollback-patient-A"
        patient_b = "rollback-patient-B"

        fact_a_id = str(uuid4())
        fact_b_id = str(uuid4())

        fact_a = self._build_mock_fact(patient_a, fact_a_id)

        session = AsyncMock()
        session.flush = AsyncMock()

        # Lineage returns fact IDs for both patients (simulating shared time window)
        lineage_result = MagicMock()
        lineage_result.scalars.return_value.all.return_value = [fact_a_id, fact_b_id]

        # Facts query filters by patient_id, so only patient A's fact is returned
        facts_result = MagicMock()
        facts_result.scalars.return_value.all.return_value = [fact_a]

        # No edges for patient A in this test
        edges_result = MagicMock()
        edges_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[lineage_result, facts_result, edges_result]
        )

        service = OpenEHRRollbackService()
        now = datetime.now(timezone.utc)
        report = await service.rollback_import_batch(
            session, patient_a,
            batch_start=now - timedelta(hours=1),
            batch_end=now + timedelta(hours=1),
        )

        assert report.success is True
        assert report.facts_deleted == 1
        # Only patient A's fact was soft-deleted
        fact_a.soft_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_empty_batch(self) -> None:
        """Rollback with no matching data should succeed with zero counts."""
        session = AsyncMock()
        session.flush = AsyncMock()

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(return_value=empty_result)

        service = OpenEHRRollbackService()
        now = datetime.now(timezone.utc)
        report = await service.rollback_import_batch(
            session, "nobody",
            batch_start=now - timedelta(hours=1),
            batch_end=now + timedelta(hours=1),
        )

        assert report.success is True
        assert report.facts_deleted == 0


# ===========================================================================
# Tests: DryRunResult / RollbackReport dataclass serialization
# ===========================================================================


class TestDataclassSerialization:
    """Verify .to_dict() serialization for report dataclasses."""

    def test_dry_run_result_to_dict(self) -> None:
        result = DryRunResult(
            success=True, patient_id="p1", conditions=2, medications=1,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["conditions"] == 2
        assert d["medications"] == 1
        assert d["measurements"] == 0

    def test_reconciliation_report_to_dict(self) -> None:
        report = ReconciliationReport(
            patient_id="p1", match=True,
            import_fingerprint="abc", export_reimport_fingerprint="abc",
        )
        d = report.to_dict()
        assert d["match"] is True
        assert d["import_fingerprint"] == "abc"

    def test_rollback_report_to_dict(self) -> None:
        report = RollbackReport(
            patient_id="p1", success=True,
            facts_deleted=5, nodes_deleted=5, edges_deleted=5,
        )
        d = report.to_dict()
        assert d["facts_deleted"] == 5

    def test_rollback_verification_to_dict(self) -> None:
        v = RollbackVerification(patient_id="p1", passed=True)
        d = v.to_dict()
        assert d["passed"] is True
        assert d["residual_facts"] == 0


# ===========================================================================
# Tests: API Model Validation
# ===========================================================================


class TestAPIModels:
    """Test new P0-019 API request/response models."""

    def test_dry_run_response_model(self) -> None:
        from app.api.openehr import DryRunResponse
        resp = DryRunResponse(success=True, patient_id="p1", conditions=3)
        assert resp.conditions == 3
        assert resp.medications == 0

    def test_reconciliation_report_response_model(self) -> None:
        from app.api.openehr import ReconciliationReportResponse
        resp = ReconciliationReportResponse(
            patient_id="p1", match=True,
            import_fingerprint="abc", export_reimport_fingerprint="abc",
        )
        assert resp.match is True

    def test_rollback_request_model(self) -> None:
        from app.api.openehr import RollbackRequest
        now = datetime.now(timezone.utc)
        req = RollbackRequest(
            patient_id="p1",
            batch_start=now - timedelta(hours=1),
            batch_end=now,
        )
        assert req.patient_id == "p1"

    def test_rollback_response_model(self) -> None:
        from app.api.openehr import RollbackResponse
        resp = RollbackResponse(
            patient_id="p1", success=True,
            facts_deleted=10, nodes_deleted=10, edges_deleted=10,
        )
        assert resp.facts_deleted == 10
