from pathlib import Path

from loglab.loader import load

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_rows():
    rows = load(FIXTURES / "access_boundary.csv")
    assert len(rows) == 6
    assert rows[0] == {"timestamp": "2025-03-01T10:00:10", "path": "/a",
                       "status": "200", "bytes": "100"}
