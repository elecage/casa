"""입력 어댑터가 도는지 본다.

여기서 보는 것은 **모양**이다 — 원천마다 레코드가 나오는지, 상태 값이
아는 것 중 하나인지, 시각이 파싱되는지. 값이 맞는지는 여기서 안 본다.
값은 `docs/reports/expected.md`의 손으로 센 기대값과 견준다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from opsbox.ingest import ADAPTERS, read_all
from opsbox.record import Record, is_billable

DATA = Path(__file__).resolve().parents[1] / "data"


def test_every_registered_adapter_reads_something():
    records = read_all(DATA)
    seen = {r.source for r in records}
    assert seen == set(ADAPTERS), f"안 읽힌 원천: {set(ADAPTERS) - seen}"


def test_records_carry_the_shape_the_rest_of_the_tool_expects():
    for record in read_all(DATA):
        assert isinstance(record, Record)
        assert isinstance(record.at, datetime)
        assert isinstance(record.units, int)
        assert record.status in {"ok", "adjusted", "void"}
        assert record.account.strip() == record.account


def test_void_records_are_the_only_ones_left_out():
    records = read_all(DATA)
    assert [r for r in records if not is_billable(r)]
    for record in records:
        assert is_billable(record) is (record.status != "void")
