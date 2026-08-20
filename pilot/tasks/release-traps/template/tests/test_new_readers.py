"""새로 붙은 원천 어댑터가 레코드를 내놓는가.

수량이 맞는지는 여기서 보지 않는다 — 원천마다 어느 열이 사용량인지는
`docs/readers/` 명세가 정한다.
"""

from pathlib import Path

from usagectl.readers import ssc, sjs, sth

DATA = Path(__file__).resolve().parents[1] / "data"


def test_ssc_skips_comment_lines():
    records = ssc.read(DATA / "ssc-2026-07.txt")
    assert len(records) == 3
    assert all(r.source == "ssc" for r in records)


def test_sth_reads_the_header_row():
    records = sth.read(DATA / "sth-2026-07.tsv")
    assert len(records) == 3
    assert records[0].account == "acct-008"


def test_sjs_uses_the_state_field():
    records = sjs.read(DATA / "sjs-2026-07.jsonl")
    assert {r.status for r in records} == {"ok", "adjusted"}
