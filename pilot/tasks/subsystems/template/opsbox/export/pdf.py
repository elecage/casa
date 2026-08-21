"""리포트 한 장을 PDF로 낸다. 모양은 `docs/export.md`."""

from __future__ import annotations

from pathlib import Path


def write(path, report: dict, title: str = "opsbox 사용량") -> None:
    from vendor.minipdf import write_table

    rows = [("기록 수", report["record_count"]),
            ("사용량 합계", report["total_units"])]
    rows += [(f"원천 {name}", value)
             for name, value in report["by_source"].items()]
    write_table(Path(path), title, rows)
