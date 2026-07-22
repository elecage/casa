from pathlib import Path

from loglab.aggregate import summarize
from loglab.loader import load
from loglab.parser import parse_rows
from loglab.windowing import assign

FIXTURES = Path(__file__).parent / "fixtures"


def _stats():
    records = parse_rows(load(FIXTURES / "access_boundary.csv"))
    return summarize(assign(records, 300))


def test_window_counts_are_half_open():
    # 10:05:00 sits exactly on a boundary -> belongs to the 10:05 window.
    assert [s.count for s in _stats()] == [3, 3]


def test_window_bytes_and_errors():
    stats = _stats()
    assert [s.bytes_total for s in stats] == [300, 500]
    assert [s.errors for s in stats] == [1, 0]
