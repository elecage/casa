"""In-memory job queue."""

from __future__ import annotations

from .settings import Settings


class JobQueue:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs: list[dict] = []

    def enqueue(self, job_id: str, submitted_at_ms: int) -> None:
        self.jobs.append({"id": job_id, "submitted_at_ms": submitted_at_ms})

    def expiry_for(self, submitted_at_ms: int) -> int:
        """Absolute time (ms) after which a job is considered stale —
        submission time plus the configured deadline_ms."""
        return submitted_at_ms + self.settings.deadline_ms
