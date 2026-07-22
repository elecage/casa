from pathlib import Path

from loglab import run

FIXTURES = Path(__file__).parent / "fixtures"


def test_report_normalizes_mixed_timezones():
    result = run([FIXTURES / "access_mixed_tz.csv"])
    assert result["windows"] == [
        {"start": "2025-03-01T09:55:00", "count": 2, "errors": 0, "bytes": 300},
        {"start": "2025-03-01T10:00:00", "count": 0, "errors": 0, "bytes": 0},
        {"start": "2025-03-01T10:05:00", "count": 3, "errors": 1, "bytes": 500},
    ]


def test_report_totals():
    result = run([FIXTURES / "access_mixed_tz.csv"])
    assert result["totals"] == {"records": 5, "errors": 1, "bytes": 800}
