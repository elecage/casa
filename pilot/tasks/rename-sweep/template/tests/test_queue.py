from jobq.queue import JobQueue
from jobq.settings import Settings


def _settings(**overrides):
    base = dict(deadline_ms=100, max_retries=1, batch_size=5, queue_name="q")
    base.update(overrides)
    return Settings(**base)


def test_expiry_is_submission_plus_deadline():
    queue = JobQueue(_settings(deadline_ms=150))
    assert queue.expiry_for(1000) == 1150
