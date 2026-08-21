"""내보내기가 도는지 본다.

**모양만 본다.** 같은 입력이면 같은 바이트가 나와야 한다는 것은
`docs/export.md`가 요구하는 것이고, 지금은 안 지켜진다. 그것을 여기서
고정하면 정할 자리가 없어지므로 여기서는 안 본다.
"""

from __future__ import annotations

from pathlib import Path

from opsbox.export import COLUMNS, to_csv
from opsbox.ingest import read_all
from opsbox.report import build

ROOT = Path(__file__).resolve().parents[1]


def _report():
    return build(read_all(ROOT / "data"))


def test_the_flat_export_carries_the_column_names_in_order():
    text = to_csv(_report())
    header = [line for line in text.splitlines() if not line.startswith("#")][0]
    assert header.split(",") == list(COLUMNS)


def test_every_account_in_the_report_comes_out():
    report = _report()
    text = to_csv(report)
    for account in report["by_account"]:
        assert account in text
