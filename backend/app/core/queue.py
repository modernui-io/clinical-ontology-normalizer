"""Redis queue configuration and job management."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.redis import get_redis

# RQ is optional - allows app to run without queue support
try:
    from rq import Queue
    from rq.job import Job

    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False
    if TYPE_CHECKING:
        from rq import Queue
        from rq.job import Job

# Lazy initialized queues cache
_queues: dict[str, "Queue"] = {}


def _check_rq_available() -> None:
    """Raise error if RQ is not available."""
    if not RQ_AVAILABLE:
        raise ImportError("RQ package is not installed. Install with: pip install rq")


def get_queue(name: str = "default") -> "Queue":
    """Get RQ queue with specified name.

    Uses cached queue instances to avoid creating multiple connections.

    Args:
        name: Queue name. Defaults to "default".

    Returns:
        RQ Queue instance.

    Raises:
        ImportError: If RQ package is not installed.
    """
    _check_rq_available()
    if name not in _queues:
        _queues[name] = Queue(name=name, connection=get_redis())
    return _queues[name]


def enqueue_job(
    func: Any,
    *args: Any,
    queue_name: str = "default",
    job_timeout: int = 600,
    job_id: str | UUID | None = None,
    **kwargs: Any,
) -> "Job":
    """Enqueue a job to the Redis queue.

    Args:
        func: The function to execute.
        *args: Positional arguments for the function.
        queue_name: Name of the queue. Defaults to "default".
        job_timeout: Job timeout in seconds. Defaults to 600 (10 minutes).
        job_id: Optional custom job ID (string or UUID).
        **kwargs: Keyword arguments for the function.

    Returns:
        RQ Job instance with job_id.

    Raises:
        ImportError: If RQ package is not installed.
    """
    queue = get_queue(queue_name)
    job_id_str = str(job_id) if job_id is not None else None
    return queue.enqueue(func, *args, job_timeout=job_timeout, job_id=job_id_str, **kwargs)


def get_job(job_id: str | UUID) -> "Job | None":
    """Get job by ID.

    Args:
        job_id: The job ID to look up (string or UUID).

    Returns:
        Job instance or None if not found.

    Raises:
        ImportError: If RQ package is not installed.
    """
    _check_rq_available()
    job_id_str = str(job_id) if isinstance(job_id, UUID) else job_id
    try:
        return Job.fetch(job_id_str, connection=get_redis())
    except Exception:
        return None


def get_job_status(job_id: str | UUID) -> str | None:
    """Get the current status of a job.

    Args:
        job_id: The job ID to check (string or UUID).

    Returns:
        Job status string ('queued', 'started', 'finished', 'failed') or None if not found.
    """
    job = get_job(job_id)
    if job is None:
        return None
    status = job.get_status()
    return str(status) if status is not None else None


def get_job_result(job_id: str | UUID) -> Any:
    """Get the result of a completed job.

    Args:
        job_id: The job ID to check (string or UUID).

    Returns:
        Job result or None if job not found or not completed.
    """
    job = get_job(job_id)
    if job is None:
        return None
    return job.result


def clear_queues() -> None:
    """Clear all queues and reset queue cache.

    Used primarily for testing cleanup.
    Safe to call even if RQ is not installed.
    """
    if RQ_AVAILABLE:
        for queue in _queues.values():
            queue.empty()
    _queues.clear()


# Queue names for different job types
QUEUE_NAMES = {
    "document": "document_processing",
    "nlp": "nlp_processing",
    "mapping": "concept_mapping",
    "graph": "graph_building",
    "export": "data_export",
    "pipeline": "pipeline_processing",  # VP-DevOps-5: Data pipeline execution
}


def get_document_queue() -> "Queue":
    """Get the document processing queue."""
    return get_queue(QUEUE_NAMES["document"])


def get_nlp_queue() -> "Queue":
    """Get the NLP processing queue."""
    return get_queue(QUEUE_NAMES["nlp"])


def get_mapping_queue() -> "Queue":
    """Get the concept mapping queue."""
    return get_queue(QUEUE_NAMES["mapping"])


def get_graph_queue() -> "Queue":
    """Get the graph building queue."""
    return get_queue(QUEUE_NAMES["graph"])


def get_export_queue() -> "Queue":
    """Get the data export queue."""
    return get_queue(QUEUE_NAMES["export"])
