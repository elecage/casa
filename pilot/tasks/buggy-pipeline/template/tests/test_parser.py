from datetime import datetime

from loglab.parser import parse_row


def test_parse_naive_utc_row():
    rec = parse_row({"timestamp": "2025-03-01T10:00:10", "path": "/a",
                     "status": "200", "bytes": "100"})
    assert rec.ts == datetime(2025, 3, 1, 10, 0, 10)
    assert rec.path == "/a"
    assert rec.status == 200
    assert rec.bytes_sent == 100


def test_parse_explicit_utc_offset_row():
    rec = parse_row({"timestamp": "2025-03-01T10:00:10+00:00", "path": "/a",
                     "status": "200", "bytes": "100"})
    assert rec.ts == datetime(2025, 3, 1, 10, 0, 10)
