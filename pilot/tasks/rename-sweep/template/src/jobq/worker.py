"""Worker loop helpers."""

from __future__ import annotations

from .queue import JobQueue


def sweep_stale(queue: JobQueue, now_ms: int) -> list[str]:
    """Drop every job whose expiry (submission + timeout_ms) has passed;
    return the dropped ids."""
    dropped = []
    kept = []
    for job in queue.jobs:
        if now_ms > queue.expiry_for(job["submitted_at_ms"]):
            dropped.append(job["id"])
        else:
            kept.append(job)
    queue.jobs = kept
    return dropped
