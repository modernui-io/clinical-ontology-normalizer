"""Tests for VP-Data ETL checkpoint and recovery system."""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.etl_checkpoint import (
    CheckpointManager,
    ETLCheckpoint,
    get_checkpoint_manager,
)


class TestETLCheckpoint:
    """Tests for ETLCheckpoint dataclass."""

    def test_checkpoint_creation(self) -> None:
        """Test creating a checkpoint."""
        checkpoint = ETLCheckpoint(
            job_id="test-job-123",
            phase="extracting_patients",
            records_processed={"patients": 100, "visits": 50},
            last_record_id="patient-100",
        )

        assert checkpoint.job_id == "test-job-123"
        assert checkpoint.phase == "extracting_patients"
        assert checkpoint.records_processed["patients"] == 100
        assert checkpoint.last_record_id == "patient-100"

    def test_checkpoint_to_dict(self) -> None:
        """Test serializing checkpoint to dictionary."""
        checkpoint = ETLCheckpoint(
            job_id="test-job-456",
            phase="extracting_visits",
            records_processed={"patients": 200},
            source_patient_mapping={"p1": 1, "p2": 2},
        )

        data = checkpoint.to_dict()

        assert data["job_id"] == "test-job-456"
        assert data["phase"] == "extracting_visits"
        assert data["records_processed"] == {"patients": 200}
        assert data["source_patient_mapping"] == {"p1": 1, "p2": 2}

    def test_checkpoint_from_dict(self) -> None:
        """Test deserializing checkpoint from dictionary."""
        data = {
            "job_id": "test-job-789",
            "phase": "extracting_conditions",
            "records_processed": {"conditions": 500},
            "last_record_id": "cond-500",
            "phases_completed": ["extracting_patients", "extracting_visits"],
            "errors_count": 5,
            "timestamp": "2026-01-28T12:00:00+00:00",
            "metadata": {"source": "fhir"},
        }

        checkpoint = ETLCheckpoint.from_dict(data)

        assert checkpoint.job_id == "test-job-789"
        assert checkpoint.phase == "extracting_conditions"
        assert checkpoint.records_processed == {"conditions": 500}
        assert len(checkpoint.phases_completed) == 2
        assert checkpoint.errors_count == 5


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir: Path) -> CheckpointManager:
        """Create a checkpoint manager with temp directory."""
        return CheckpointManager(temp_dir)

    def test_save_and_load_checkpoint(self, manager: CheckpointManager) -> None:
        """Test saving and loading a checkpoint."""
        checkpoint = ETLCheckpoint(
            job_id="save-load-test",
            phase="extracting_drugs",
            records_processed={"drugs": 150},
            last_record_id="drug-150",
        )

        # Save checkpoint
        result = manager.save_checkpoint(checkpoint)
        assert result is True

        # Load checkpoint
        loaded = manager.load_checkpoint("save-load-test")
        assert loaded is not None
        assert loaded.job_id == "save-load-test"
        assert loaded.phase == "extracting_drugs"
        assert loaded.records_processed == {"drugs": 150}

    def test_load_nonexistent_checkpoint(self, manager: CheckpointManager) -> None:
        """Test loading a checkpoint that doesn't exist."""
        result = manager.load_checkpoint("nonexistent-job")
        assert result is None

    def test_delete_checkpoint(self, manager: CheckpointManager) -> None:
        """Test deleting a checkpoint."""
        # Create and save checkpoint
        checkpoint = ETLCheckpoint(
            job_id="delete-test",
            phase="extracting_patients",
        )
        manager.save_checkpoint(checkpoint)

        # Verify it exists
        assert manager.load_checkpoint("delete-test") is not None

        # Delete it
        result = manager.delete_checkpoint("delete-test")
        assert result is True

        # Verify it's gone
        assert manager.load_checkpoint("delete-test") is None

    def test_list_checkpoints(self, manager: CheckpointManager) -> None:
        """Test listing all checkpoints."""
        # Create multiple checkpoints
        for i in range(3):
            checkpoint = ETLCheckpoint(
                job_id=f"list-test-{i}",
                phase="extracting_patients",
            )
            manager.save_checkpoint(checkpoint)

        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 3

        job_ids = {cp.job_id for cp in checkpoints}
        assert "list-test-0" in job_ids
        assert "list-test-1" in job_ids
        assert "list-test-2" in job_ids

    def test_get_incomplete_jobs(self, manager: CheckpointManager) -> None:
        """Test getting incomplete jobs."""
        # Create complete job
        complete = ETLCheckpoint(
            job_id="complete-job",
            phase="finalizing",
            phases_completed=["extracting_patients", "extracting_visits", "finalizing"],
        )
        manager.save_checkpoint(complete)

        # Create incomplete job
        incomplete = ETLCheckpoint(
            job_id="incomplete-job",
            phase="extracting_visits",
            phases_completed=["extracting_patients"],
        )
        manager.save_checkpoint(incomplete)

        incomplete_jobs = manager.get_incomplete_jobs()
        assert len(incomplete_jobs) == 1
        assert incomplete_jobs[0].job_id == "incomplete-job"

    def test_checkpoint_with_mappings(self, manager: CheckpointManager) -> None:
        """Test checkpoint with patient/visit mappings."""
        checkpoint = ETLCheckpoint(
            job_id="mapping-test",
            phase="extracting_conditions",
            source_patient_mapping={
                "patient-a": 1001,
                "patient-b": 1002,
                "patient-c": 1003,
            },
            source_visit_mapping={
                "visit-x": 2001,
                "visit-y": 2002,
            },
        )

        manager.save_checkpoint(checkpoint)
        loaded = manager.load_checkpoint("mapping-test")

        assert loaded is not None
        assert loaded.source_patient_mapping["patient-a"] == 1001
        assert loaded.source_patient_mapping["patient-c"] == 1003
        assert loaded.source_visit_mapping["visit-x"] == 2001

    def test_checkpoint_update(self, manager: CheckpointManager) -> None:
        """Test updating an existing checkpoint."""
        # Create initial checkpoint
        checkpoint1 = ETLCheckpoint(
            job_id="update-test",
            phase="extracting_patients",
            records_processed={"patients": 50},
        )
        manager.save_checkpoint(checkpoint1)

        # Update checkpoint
        checkpoint2 = ETLCheckpoint(
            job_id="update-test",
            phase="extracting_visits",
            records_processed={"patients": 100, "visits": 25},
            phases_completed=["extracting_patients"],
        )
        manager.save_checkpoint(checkpoint2)

        # Load and verify update
        loaded = manager.load_checkpoint("update-test")
        assert loaded is not None
        assert loaded.phase == "extracting_visits"
        assert loaded.records_processed["patients"] == 100
        assert loaded.records_processed["visits"] == 25


class TestCheckpointRecovery:
    """Tests for ETL recovery scenarios."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_recovery_scenario(self, temp_dir: Path) -> None:
        """Test a realistic recovery scenario."""
        manager = CheckpointManager(temp_dir)

        # Simulate job progress with checkpoints
        job_id = "recovery-test-job"

        # First phase
        cp1 = ETLCheckpoint(
            job_id=job_id,
            phase="extracting_patients",
            records_processed={"patients": 500},
            last_record_id="patient-500",
            source_patient_mapping={f"p-{i}": i for i in range(1, 501)},
            phases_completed=[],
        )
        manager.save_checkpoint(cp1)

        # Second phase
        cp2 = ETLCheckpoint(
            job_id=job_id,
            phase="extracting_visits",
            records_processed={"patients": 500, "visits": 200},
            last_record_id="visit-200",
            source_patient_mapping=cp1.source_patient_mapping,
            source_visit_mapping={f"v-{i}": i for i in range(1, 201)},
            phases_completed=["extracting_patients"],
        )
        manager.save_checkpoint(cp2)

        # Simulate crash and recovery
        new_manager = CheckpointManager(temp_dir)
        recovered = new_manager.load_checkpoint(job_id)

        assert recovered is not None
        assert recovered.phase == "extracting_visits"
        assert recovered.records_processed["patients"] == 500
        assert recovered.records_processed["visits"] == 200
        assert len(recovered.source_patient_mapping) == 500
        assert len(recovered.source_visit_mapping) == 200
        assert "extracting_patients" in recovered.phases_completed
