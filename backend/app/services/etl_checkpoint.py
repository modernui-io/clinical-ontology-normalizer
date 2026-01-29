"""VP-Data: ETL Checkpoint and Recovery System.

Provides persistent checkpointing for ETL jobs to enable:
- Recovery from failures (resume from last checkpoint)
- Progress tracking across process restarts
- Audit trail of ETL processing

Checkpoints are stored in JSON files with the following structure:
- job_id: Unique identifier
- phase: Current ETL phase
- records_processed: Count per record type
- last_record_id: Last successfully processed record
- source_mappings: patient_id -> person_id mappings
- timestamp: When checkpoint was saved
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class ETLCheckpoint:
    """Checkpoint data for an ETL job.

    Stores enough information to resume a failed job from
    the last successfully processed record.
    """

    job_id: str
    phase: str
    records_processed: dict[str, int] = field(default_factory=dict)
    last_record_id: str | None = None
    source_patient_mapping: dict[str, int] = field(default_factory=dict)
    source_visit_mapping: dict[str, int] = field(default_factory=dict)
    phases_completed: list[str] = field(default_factory=list)
    errors_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ETLCheckpoint":
        """Create from dictionary."""
        return cls(
            job_id=data["job_id"],
            phase=data["phase"],
            records_processed=data.get("records_processed", {}),
            last_record_id=data.get("last_record_id"),
            source_patient_mapping=data.get("source_patient_mapping", {}),
            source_visit_mapping=data.get("source_visit_mapping", {}),
            phases_completed=data.get("phases_completed", []),
            errors_count=data.get("errors_count", 0),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
        )


class CheckpointManager:
    """Manages ETL job checkpoints.

    Provides methods to save, load, and manage checkpoints
    for ETL jobs to enable recovery from failures.

    Usage:
        manager = CheckpointManager()

        # Save checkpoint during processing
        checkpoint = ETLCheckpoint(
            job_id="abc123",
            phase="extracting_patients",
            records_processed={"patients": 150},
            last_record_id="patient-150",
        )
        manager.save_checkpoint(checkpoint)

        # Recover after failure
        checkpoint = manager.load_checkpoint("abc123")
        if checkpoint:
            print(f"Resuming from phase {checkpoint.phase}")
    """

    def __init__(self, checkpoint_dir: str | Path | None = None):
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files.
                           Defaults to .etl_checkpoints in current directory.
        """
        if checkpoint_dir is None:
            checkpoint_dir = Path.cwd() / ".etl_checkpoints"

        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CheckpointManager initialized with dir: {self._checkpoint_dir}")

    def _get_checkpoint_path(self, job_id: str | UUID) -> Path:
        """Get the path to a checkpoint file."""
        return self._checkpoint_dir / f"{job_id}.json"

    def save_checkpoint(self, checkpoint: ETLCheckpoint) -> bool:
        """Save a checkpoint to disk.

        Args:
            checkpoint: The checkpoint to save.

        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            path = self._get_checkpoint_path(checkpoint.job_id)

            # Update timestamp
            checkpoint.timestamp = datetime.now(timezone.utc).isoformat()

            # Write atomically using temp file
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, default=str)

            # Atomic rename
            temp_path.replace(path)

            logger.debug(
                f"Saved checkpoint for job {checkpoint.job_id} at phase {checkpoint.phase}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint for {checkpoint.job_id}: {e}", exc_info=True)
            return False

    def load_checkpoint(self, job_id: str | UUID) -> ETLCheckpoint | None:
        """Load a checkpoint from disk.

        Args:
            job_id: The job ID to load checkpoint for.

        Returns:
            ETLCheckpoint if found, None otherwise.
        """
        try:
            path = self._get_checkpoint_path(str(job_id))

            if not path.exists():
                return None

            with open(path) as f:
                data = json.load(f)

            checkpoint = ETLCheckpoint.from_dict(data)
            logger.debug(f"Loaded checkpoint for job {job_id}")
            return checkpoint

        except Exception as e:
            logger.error(f"Failed to load checkpoint for {job_id}: {e}", exc_info=True)
            return None

    def delete_checkpoint(self, job_id: str | UUID) -> bool:
        """Delete a checkpoint file.

        Args:
            job_id: The job ID to delete checkpoint for.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            path = self._get_checkpoint_path(str(job_id))

            if path.exists():
                path.unlink()
                logger.debug(f"Deleted checkpoint for job {job_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete checkpoint for {job_id}: {e}", exc_info=True)
            return False

    def list_checkpoints(self) -> list[ETLCheckpoint]:
        """List all available checkpoints.

        Returns:
            List of all checkpoints found.
        """
        checkpoints = []

        try:
            for path in self._checkpoint_dir.glob("*.json"):
                try:
                    with open(path) as f:
                        data = json.load(f)
                    checkpoints.append(ETLCheckpoint.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint {path}: {e}")

        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}", exc_info=True)

        return checkpoints

    def get_incomplete_jobs(self) -> list[ETLCheckpoint]:
        """Get checkpoints for jobs that haven't completed.

        Returns:
            List of checkpoints for incomplete jobs.
        """
        checkpoints = self.list_checkpoints()

        # Filter to jobs that haven't reached "finalizing" phase
        incomplete = [
            cp for cp in checkpoints
            if "finalizing" not in cp.phases_completed
        ]

        return incomplete

    def cleanup_old_checkpoints(self, max_age_days: int = 7) -> int:
        """Remove checkpoints older than specified age.

        Args:
            max_age_days: Maximum age in days to keep checkpoints.

        Returns:
            Number of checkpoints removed.
        """
        removed = 0
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)

        for checkpoint in self.list_checkpoints():
            try:
                cp_time = datetime.fromisoformat(
                    checkpoint.timestamp.replace("Z", "+00:00")
                ).timestamp()

                if cp_time < cutoff:
                    if self.delete_checkpoint(checkpoint.job_id):
                        removed += 1

            except Exception as e:
                logger.warning(f"Error checking checkpoint age: {e}")

        logger.info(f"Cleaned up {removed} old checkpoints")
        return removed


# Singleton instance
_checkpoint_manager: CheckpointManager | None = None
_checkpoint_lock = threading.Lock()


def get_checkpoint_manager(checkpoint_dir: str | Path | None = None) -> CheckpointManager:
    """Get or create the singleton checkpoint manager.

    Args:
        checkpoint_dir: Optional directory for checkpoints.

    Returns:
        CheckpointManager singleton instance.
    """
    global _checkpoint_manager

    # VP-ThreadSafety: Double-checked locking for thread safety
    if _checkpoint_manager is None:
        with _checkpoint_lock:
            if _checkpoint_manager is None:
                _checkpoint_manager = CheckpointManager(checkpoint_dir)

    return _checkpoint_manager
