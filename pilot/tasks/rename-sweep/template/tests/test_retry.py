from jobq.retry import backoff_ms, schedule_ms


def test_backoff_doubles_and_caps():
    assert backoff_ms(1) == 100
    assert backoff_ms(3) == 400
    assert backoff_ms(6) == 1000


def test_schedule_matches_backoff():
    assert schedule_ms(3) == [100, 200, 400]
