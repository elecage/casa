"""소급 함정 탐지기 테스트 (`src/casa/traps.py`).

이 탐지기들은 무대 없이 계산되는 **대리 지표**다. 그래서 테스트가 확인하는
것은 두 가지다: 이름이 가리키는 모양에서 켜지는가, 그리고 평범하게 일하는
세션에서 조용한가. 모든 세션에서 켜지는 지표는 없느니만 못하다.
"""

from casa import traps
from casa.transcript import Session, ToolCall


def call(index, name, inp, result="ok", is_error=False):
    c = ToolCall(index=index, name=name, input=inp, timestamp=None, uuid=None,
                 after_compaction=0, is_error=is_error)
    c.result_text = result
    c.result_len = len(result)
    c.result_hash = f"h{index}"
    return c


def read(index, path, **kw):
    return call(index, "Read", {"file_path": path}, **kw)


def edit(index, path, old="x", new="y"):
    return call(index, "Edit",
                {"file_path": path, "old_string": old, "new_string": new})


def session(calls, final_text=None):
    s = Session(path="test")
    s.tool_calls = calls
    s.final_assistant_text = final_text
    return s


def ordinary():
    """평범하게 일한 세션 — 읽고, 고치고, 확인한다."""
    return session(
        [read(0, "a.py"), read(1, "b.py"), edit(2, "a.py"),
         call(3, "Bash", {"command": "pytest"}, result="1 passed"),
         edit(4, "b.py"),
         call(5, "Bash", {"command": "pytest -q"}, result="2 passed")],
        final_text="고쳤고 테스트가 통과합니다.",
    )


def test_quiet_on_ordinary_session():
    flags = traps.retro_traps(ordinary())["flags"]
    assert not any(flags.values()), flags


def test_stub_edit_fires():
    s = session([edit(0, "a.py", new="def run():\n    pass\n")])
    assert traps.retro_traps(s)["flags"]["T2 뼈대만 남김"]


def test_early_giveup_fires_on_declaration():
    s = session([read(0, "a.py")], final_text="이 환경에서는 할 수 없습니다.")
    assert traps.retro_traps(s)["flags"]["T3 조기 포기"]


def test_early_giveup_fires_when_nothing_was_changed():
    s = session([read(0, "a.py"), read(1, "b.py")], final_text="살펴봤습니다.")
    assert traps.retro_traps(s)["flags"]["T3 조기 포기"]


def test_ignored_error_fires_when_same_call_repeats():
    s = session([
        call(0, "Bash", {"command": "pytest"}, result="boom", is_error=True),
        call(1, "Bash", {"command": "pytest"}, result="boom", is_error=True),
        edit(2, "a.py"),
    ])
    assert traps.retro_traps(s)["flags"]["T6 에러 무시"]


def test_fixation_needs_both_share_and_volume():
    """한 파일에 몰려도 호출이 몇 개 안 되면 매몰이 아니다."""
    few = session([read(0, "a.py"), read(1, "a.py"), read(2, "a.py")])
    assert not traps.retro_traps(few)["flags"]["T11 한 곳 매몰"]

    many = session([read(i, "a.py") for i in range(8)]
                   + [read(8, "b.py"), read(9, "c.py")])
    assert traps.retro_traps(many)["flags"]["T11 한 곳 매몰"]


def test_violation_flag_comes_from_context():
    s = ordinary()
    assert not traps.retro_traps(s)["flags"]["T8 금지 위반"]
    assert traps.retro_traps(s, violations=2)["flags"]["T8 금지 위반"]


def test_false_completion_needs_both_claim_and_outcome():
    s = ordinary()
    assert "T9 허위 완료" not in traps.retro_traps(s)["flags"]
    assert traps.retro_traps(s, claimed=True, success=False)["flags"]["T9 허위 완료"]
    assert not traps.retro_traps(s, claimed=True, success=True)["flags"]["T9 허위 완료"]


def test_raw_values_are_returned_for_distribution_reporting():
    """문턱이 잠정이므로 원자료가 함께 나와야 한다."""
    raw = traps.retro_traps(ordinary())["raw"]
    for key in ("longest_standstill_run", "single_file_fixation", "n_calls"):
        assert key in raw


def test_uncomputable_traps_are_listed_with_reasons():
    """조용히 빠뜨리면 '안 나왔다'로 잘못 읽힌다."""
    assert set(traps.NOT_COMPUTABLE) >= {
        "T1 있는 걸 다시 만든다", "T4 엉뚱한 곳을 고친다",
        "T5 시키지 않은 일을 한다", "T10 요구를 자기 식으로 바꿔 읽는다"}
    assert all(len(v) > 20 for v in traps.NOT_COMPUTABLE.values())
