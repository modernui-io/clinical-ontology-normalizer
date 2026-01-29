"""Job Queue Management Service.

Provides queue statistics, worker status monitoring,
job retry/cancel operations, and wait time estimation.

VP-Memory-2: History collections bounded with deque to prevent memory growth.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import logging
import random
import threading
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class JobStatus(str, Enum):
    """Status of a job in the queue."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(str, Enum):
    """Priority levels for jobs."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WorkerState(str, Enum):
    """State of a worker."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    DRAINING = "draining"


@dataclass
class Job:
    """A job in the processing queue."""

    id: str
    job_type: str
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    worker_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    position_in_queue: int | None = None
    estimated_duration_seconds: float | None = None


@dataclass
class RetryAttempt:
    """A retry attempt for a job."""

    attempt_number: int
    timestamp: str
    error: str
    worker_id: str | None = None
    duration_seconds: float | None = None


@dataclass
class WorkerStatus:
    """Status of a queue worker."""

    worker_id: str
    name: str
    state: WorkerState = WorkerState.IDLE
    current_job_id: str | None = None
    current_job_type: str | None = None
    jobs_completed: int = 0
    jobs_failed: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    avg_processing_time_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


@dataclass
class QueueStats:
    """Statistics for the job queue."""

    pending_count: int = 0
    queued_count: int = 0
    running_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    total_count: int = 0
    avg_wait_time_seconds: float = 0.0
    avg_processing_time_seconds: float = 0.0
    throughput_per_minute: float = 0.0
    oldest_pending_job_age_seconds: float = 0.0
    by_priority: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)


@dataclass
class QueueDepthPoint:
    """A point in time for queue depth history."""

    timestamp: str
    pending: int
    running: int
    completed: int
    failed: int


@dataclass
class ProcessingRate:
    """Processing rate metrics."""

    jobs_per_minute: float
    jobs_per_hour: float
    avg_duration_seconds: float
    success_rate: float
    error_rate: float
    trend: str  # "increasing", "decreasing", "stable"


# ============================================================================
# Job Queue Service
# ============================================================================


class JobQueueService:
    """Service for managing the job queue."""

    def __init__(self):
        """Initialize the job queue service.

        VP-Memory-2: History collections bounded with deque to prevent OOM.
        """
        self._jobs: dict[str, Job] = {}
        self._retry_history: dict[str, list[RetryAttempt]] = defaultdict(list)
        self._workers: dict[str, WorkerStatus] = {}
        # VP-Memory-2: Bounded history collections
        self._queue_depth_history: deque[QueueDepthPoint] = deque(maxlen=1440)  # 24h @ 1min
        self._lock = threading.Lock()
        self._processing_times: deque[float] = deque(maxlen=1000)  # Last 1000 jobs
        self._completion_timestamps: deque[datetime] = deque(maxlen=10000)  # Last 10k

        # Initialize with mock data
        self._initialize_mock_data()

    def _initialize_mock_data(self) -> None:
        """Initialize with mock data for demonstration."""
        # Create some mock workers
        worker_names = [
            "worker-nlp-1",
            "worker-nlp-2",
            "worker-mapping-1",
            "worker-mapping-2",
            "worker-graph-1",
        ]

        for i, name in enumerate(worker_names):
            worker_id = f"worker-{uuid.uuid4().hex[:8]}"
            state = random.choice([WorkerState.IDLE, WorkerState.BUSY, WorkerState.IDLE])
            self._workers[worker_id] = WorkerStatus(
                worker_id=worker_id,
                name=name,
                state=state,
                jobs_completed=random.randint(50, 500),
                jobs_failed=random.randint(0, 10),
                avg_processing_time_seconds=random.uniform(2.0, 15.0),
                memory_usage_mb=random.uniform(256, 1024),
                cpu_usage_percent=random.uniform(10, 80),
            )

        # Create mock jobs
        job_types = [
            "document_extraction",
            "concept_mapping",
            "graph_building",
            "batch_processing",
            "fhir_export",
        ]

        # Add completed jobs
        for i in range(25):
            job_id = f"JOB-{uuid.uuid4().hex[:12]}"
            completed_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 120))
            started_time = completed_time - timedelta(seconds=random.randint(5, 60))
            created_time = started_time - timedelta(seconds=random.randint(1, 30))

            self._jobs[job_id] = Job(
                id=job_id,
                job_type=random.choice(job_types),
                status=JobStatus.COMPLETED,
                priority=random.choice(list(JobPriority)),
                created_at=created_time.isoformat(),
                started_at=started_time.isoformat(),
                completed_at=completed_time.isoformat(),
                result={"success": True},
            )
            self._processing_times.append((completed_time - started_time).total_seconds())
            self._completion_timestamps.append(completed_time)

        # Add failed jobs
        for i in range(5):
            job_id = f"JOB-{uuid.uuid4().hex[:12]}"
            failed_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(10, 60))
            started_time = failed_time - timedelta(seconds=random.randint(5, 30))
            created_time = started_time - timedelta(seconds=random.randint(1, 10))

            job = Job(
                id=job_id,
                job_type=random.choice(job_types),
                status=JobStatus.FAILED,
                priority=random.choice(list(JobPriority)),
                created_at=created_time.isoformat(),
                started_at=started_time.isoformat(),
                completed_at=failed_time.isoformat(),
                error="Processing failed: timeout exceeded",
                retry_count=random.randint(1, 3),
            )
            self._jobs[job_id] = job

            # Add retry history
            for attempt in range(job.retry_count):
                self._retry_history[job_id].append(
                    RetryAttempt(
                        attempt_number=attempt + 1,
                        timestamp=(failed_time - timedelta(minutes=5 * (job.retry_count - attempt))).isoformat(),
                        error="Temporary failure",
                        worker_id=random.choice(list(self._workers.keys())),
                        duration_seconds=random.uniform(5, 20),
                    )
                )

        # Add running jobs
        worker_ids = list(self._workers.keys())
        for i in range(3):
            job_id = f"JOB-{uuid.uuid4().hex[:12]}"
            started_time = datetime.now(timezone.utc) - timedelta(seconds=random.randint(10, 120))
            created_time = started_time - timedelta(seconds=random.randint(1, 30))

            worker_id = worker_ids[i % len(worker_ids)]
            self._jobs[job_id] = Job(
                id=job_id,
                job_type=random.choice(job_types),
                status=JobStatus.RUNNING,
                priority=random.choice(list(JobPriority)),
                created_at=created_time.isoformat(),
                started_at=started_time.isoformat(),
                worker_id=worker_id,
                estimated_duration_seconds=random.uniform(30, 120),
            )

            # Update worker status
            self._workers[worker_id].state = WorkerState.BUSY
            self._workers[worker_id].current_job_id = job_id
            self._workers[worker_id].current_job_type = self._jobs[job_id].job_type

        # Add pending/queued jobs
        for i in range(12):
            job_id = f"JOB-{uuid.uuid4().hex[:12]}"
            created_time = datetime.now(timezone.utc) - timedelta(seconds=random.randint(30, 300))

            self._jobs[job_id] = Job(
                id=job_id,
                job_type=random.choice(job_types),
                status=random.choice([JobStatus.PENDING, JobStatus.QUEUED]),
                priority=random.choice(list(JobPriority)),
                created_at=created_time.isoformat(),
                position_in_queue=i + 1,
            )

        # Generate queue depth history (last 24 hours)
        now = datetime.now(timezone.utc)
        for i in range(288):  # 5-minute intervals for 24 hours
            timestamp = now - timedelta(minutes=5 * (288 - i))
            base_pending = 10 + int(5 * abs((i % 48) - 24) / 24)
            self._queue_depth_history.append(
                QueueDepthPoint(
                    timestamp=timestamp.isoformat(),
                    pending=base_pending + random.randint(-3, 3),
                    running=3 + random.randint(-1, 1),
                    completed=random.randint(5, 15),
                    failed=random.randint(0, 2),
                )
            )

    def get_queue_stats(self) -> QueueStats:
        """Get queue statistics."""
        with self._lock:
            by_status = defaultdict(int)
            by_priority = defaultdict(int)
            by_type = defaultdict(int)
            oldest_pending_age = 0.0

            for job in self._jobs.values():
                by_status[job.status.value] += 1
                by_priority[job.priority.value] += 1
                by_type[job.job_type] += 1

                if job.status in [JobStatus.PENDING, JobStatus.QUEUED]:
                    created = datetime.fromisoformat(job.created_at)
                    age = (datetime.now(timezone.utc) - created).total_seconds()
                    oldest_pending_age = max(oldest_pending_age, age)

            # Calculate throughput (jobs completed in last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_completions = [
                t for t in self._completion_timestamps if t > one_hour_ago
            ]
            throughput = len(recent_completions) / 60.0  # per minute

            avg_processing = sum(self._processing_times[-100:]) / max(len(self._processing_times[-100:]), 1)

            return QueueStats(
                pending_count=by_status.get("pending", 0),
                queued_count=by_status.get("queued", 0),
                running_count=by_status.get("running", 0),
                completed_count=by_status.get("completed", 0),
                failed_count=by_status.get("failed", 0),
                cancelled_count=by_status.get("cancelled", 0),
                total_count=len(self._jobs),
                avg_wait_time_seconds=30.0,  # Mock average wait time
                avg_processing_time_seconds=avg_processing,
                throughput_per_minute=throughput,
                oldest_pending_job_age_seconds=oldest_pending_age,
                by_priority=dict(by_priority),
                by_type=dict(by_type),
            )

    def get_queue_depth_history(self, hours: int = 24) -> list[QueueDepthPoint]:
        """Get queue depth over time."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            return [
                point
                for point in self._queue_depth_history
                if datetime.fromisoformat(point.timestamp) > cutoff
            ]

    def get_processing_rate(self) -> ProcessingRate:
        """Get current processing rate."""
        with self._lock:
            # Calculate jobs completed in last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_completions = [
                t for t in self._completion_timestamps if t > one_hour_ago
            ]
            jobs_per_hour = len(recent_completions)
            jobs_per_minute = jobs_per_hour / 60.0

            # Calculate success/error rates
            completed = sum(1 for j in self._jobs.values() if j.status == JobStatus.COMPLETED)
            failed = sum(1 for j in self._jobs.values() if j.status == JobStatus.FAILED)
            total_finished = completed + failed

            success_rate = (completed / total_finished * 100) if total_finished > 0 else 100.0
            error_rate = (failed / total_finished * 100) if total_finished > 0 else 0.0

            # Determine trend
            if len(self._queue_depth_history) >= 12:
                recent = self._queue_depth_history[-12:]
                early = self._queue_depth_history[-24:-12] if len(self._queue_depth_history) >= 24 else []

                recent_avg = sum(p.pending for p in recent) / len(recent)
                early_avg = sum(p.pending for p in early) / len(early) if early else recent_avg

                if recent_avg > early_avg * 1.1:
                    trend = "increasing"
                elif recent_avg < early_avg * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            avg_duration = sum(self._processing_times[-50:]) / max(len(self._processing_times[-50:]), 1)

            return ProcessingRate(
                jobs_per_minute=round(jobs_per_minute, 2),
                jobs_per_hour=jobs_per_hour,
                avg_duration_seconds=round(avg_duration, 2),
                success_rate=round(success_rate, 2),
                error_rate=round(error_rate, 2),
                trend=trend,
            )

    def estimate_wait_time(self, job_type: str) -> timedelta:
        """Estimate wait time for new job of given type."""
        with self._lock:
            # Count pending jobs of same type
            pending_same_type = sum(
                1
                for j in self._jobs.values()
                if j.status in [JobStatus.PENDING, JobStatus.QUEUED] and j.job_type == job_type
            )

            # Get average processing time
            avg_processing = sum(self._processing_times[-50:]) / max(len(self._processing_times[-50:]), 1)

            # Count available workers
            available_workers = sum(
                1 for w in self._workers.values() if w.state in [WorkerState.IDLE, WorkerState.BUSY]
            )
            available_workers = max(available_workers, 1)

            # Estimate: (pending jobs + 1) * avg_time / workers
            estimated_seconds = (pending_same_type + 1) * avg_processing / available_workers

            return timedelta(seconds=estimated_seconds)

    def get_worker_status(self) -> list[WorkerStatus]:
        """Get status of all workers."""
        with self._lock:
            return list(self._workers.values())

    def get_job(self, job_id: str) -> Job | None:
        """Get a specific job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_jobs(
        self,
        status: JobStatus | None = None,
        job_type: str | None = None,
        priority: JobPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Job], int]:
        """Get jobs with optional filtering."""
        with self._lock:
            jobs = list(self._jobs.values())

            if status:
                jobs = [j for j in jobs if j.status == status]
            if job_type:
                jobs = [j for j in jobs if j.job_type == job_type]
            if priority:
                jobs = [j for j in jobs if j.priority == priority]

            # Sort by created_at descending
            jobs.sort(key=lambda j: j.created_at, reverse=True)

            total = len(jobs)
            return jobs[offset : offset + limit], total

    def retry_job(self, job_id: str) -> Job:
        """Retry a failed job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
                raise ValueError(f"Job cannot be retried: {job.status}")

            if job.retry_count >= job.max_retries:
                raise ValueError(f"Job has exceeded max retries: {job.retry_count}/{job.max_retries}")

            # Record the retry attempt
            self._retry_history[job_id].append(
                RetryAttempt(
                    attempt_number=job.retry_count + 1,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error=job.error or "Manual retry",
                    worker_id=job.worker_id,
                )
            )

            # Reset job status
            job.status = JobStatus.QUEUED
            job.retry_count += 1
            job.error = None
            job.started_at = None
            job.completed_at = None
            job.worker_id = None

            return job

    def cancel_job(self, job_id: str) -> Job:
        """Cancel a pending or running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status not in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]:
                raise ValueError(f"Job cannot be cancelled: {job.status}")

            # If running, notify the worker
            if job.status == JobStatus.RUNNING and job.worker_id:
                worker = self._workers.get(job.worker_id)
                if worker:
                    worker.state = WorkerState.IDLE
                    worker.current_job_id = None
                    worker.current_job_type = None

            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc).isoformat()

            return job

    def get_retry_history(self, job_id: str) -> list[RetryAttempt]:
        """Get retry history for a job."""
        with self._lock:
            if job_id not in self._jobs:
                raise ValueError(f"Job not found: {job_id}")
            return self._retry_history.get(job_id, [])

    def get_job_estimate(self, job_id: str) -> dict[str, Any]:
        """Get estimated completion time for a specific job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status == JobStatus.COMPLETED:
                return {
                    "job_id": job_id,
                    "status": job.status.value,
                    "completed_at": job.completed_at,
                    "estimated_completion": None,
                    "position_in_queue": None,
                }

            if job.status == JobStatus.RUNNING:
                # Estimate based on average processing time
                avg_processing = sum(self._processing_times[-50:]) / max(len(self._processing_times[-50:]), 1)
                started = datetime.fromisoformat(job.started_at) if job.started_at else datetime.now(timezone.utc)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                remaining = max(0, avg_processing - elapsed)

                return {
                    "job_id": job_id,
                    "status": job.status.value,
                    "started_at": job.started_at,
                    "elapsed_seconds": round(elapsed, 2),
                    "estimated_remaining_seconds": round(remaining, 2),
                    "estimated_completion": (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat(),
                    "position_in_queue": None,
                }

            # For pending/queued jobs
            wait_time = self.estimate_wait_time(job.job_type)
            position = job.position_in_queue or self._calculate_position(job_id)

            return {
                "job_id": job_id,
                "status": job.status.value,
                "position_in_queue": position,
                "estimated_wait_seconds": round(wait_time.total_seconds(), 2),
                "estimated_completion": (datetime.now(timezone.utc) + wait_time).isoformat(),
            }

    def _calculate_position(self, job_id: str) -> int:
        """Calculate position in queue for a pending job."""
        job = self._jobs.get(job_id)
        if not job or job.status not in [JobStatus.PENDING, JobStatus.QUEUED]:
            return 0

        pending_jobs = [
            j
            for j in self._jobs.values()
            if j.status in [JobStatus.PENDING, JobStatus.QUEUED]
        ]
        pending_jobs.sort(key=lambda j: (
            -list(JobPriority).index(j.priority),  # Higher priority first
            j.created_at,  # Earlier jobs first
        ))

        for i, j in enumerate(pending_jobs):
            if j.id == job_id:
                return i + 1
        return 0

    def retry_all_failed(self) -> list[Job]:
        """Retry all failed jobs that haven't exceeded max retries."""
        with self._lock:
            retried = []
            for job in self._jobs.values():
                if job.status == JobStatus.FAILED and job.retry_count < job.max_retries:
                    try:
                        self._lock.release()
                        retried_job = self.retry_job(job.id)
                        self._lock.acquire()
                        retried.append(retried_job)
                    except ValueError:
                        self._lock.acquire()
                        continue
            return retried

    def cancel_selected(self, job_ids: list[str]) -> list[Job]:
        """Cancel multiple jobs."""
        cancelled = []
        for job_id in job_ids:
            try:
                job = self.cancel_job(job_id)
                cancelled.append(job)
            except ValueError:
                continue
        return cancelled

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        stats = self.get_queue_stats()
        return {
            "total_jobs": stats.total_count,
            "pending": stats.pending_count + stats.queued_count,
            "running": stats.running_count,
            "completed": stats.completed_count,
            "failed": stats.failed_count,
            "workers": len(self._workers),
            "throughput_per_minute": stats.throughput_per_minute,
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: JobQueueService | None = None
_service_lock = threading.Lock()


def get_job_queue_service() -> JobQueueService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = JobQueueService()

    return _service_instance


def reset_job_queue_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
