from jobq.queue import JobQueue
from jobq.settings import Settings
from jobq.worker import sweep_stale


def test_sweep_drops_only_expired_jobs():
    settings = Settings(deadline_ms=150, max_retries=1, batch_size=5, queue_name="q")
    queue = JobQueue(settings)
    queue.enqueue("old", submitted_at_ms=0)      # expires at 150
    queue.enqueue("fresh", submitted_at_ms=900)  # expires at 1050

    dropped = sweep_stale(queue, now_ms=1000)

    assert dropped == ["old"]
    assert [job["id"] for job in queue.jobs] == ["fresh"]
