from jobq.env import overrides


def test_env_override_coerces_duration_to_int():
    assert overrides({"JOBQ_DEADLINE_MS": "250"}) == {"deadline_ms": 250}


def test_env_override_queue_name_stays_str():
    assert overrides({"JOBQ_QUEUE_NAME": "fast"}) == {"queue_name": "fast"}
