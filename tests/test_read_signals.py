"""무엇을 읽었는가와 어떤 차례로 갔는가를 보는 지표들.

기존 지표 스무 종은 도구 호출의 모양만 본다 — 몇 번 불렀는지, 같은 것을 다시
불렀는지, 에러 뒤에 무엇을 했는지. 여기 있는 것들은 읽은 대상과 순서를 본다.

테스트가 못 박는 것은 둘이다. 지표가 이름이 말하는 모양에서 값이 오르는가,
그리고 보통 일하는 세션에서 조용한가.
"""

from casa import metrics, signals
from casa.transcript import Session, ToolCall


def call(index, name, inp, result="ok", is_error=False):
    c = ToolCall(index=index, name=name, input=inp, timestamp=None, uuid=None,
                 after_compaction=0, is_error=is_error)
    c.result_text = result
    c.result_len = len(result)
    c.result_hash = f"h{index}"
    return c


def read(index, path):
    return call(index, "Read", {"file_path": path})


def edit(index, path):
    return call(index, "Edit", {"file_path": path,
                                "old_string": "x", "new_string": "y"})


def write(index, path):
    return call(index, "Write", {"file_path": path, "content": "hello"})


def shell(index, command):
    return call(index, "Bash", {"command": command})


def session(calls):
    s = Session(path="test")
    s.tool_calls = calls
    return s


def ordinary():
    """보통 일하는 세션: 코드를 읽고, 고치고, 확인한다."""
    return [
        read(0, "a.py"), read(1, "b.py"), read(2, "c.py"),
        edit(3, "a.py"), shell(4, "pytest"),
        edit(5, "b.py"), shell(6, "pytest"),
    ]


# ------------------------------------------------- 읽은 대상을 산출하기


def test_read_targets_keeps_order_and_repeats():
    calls = [read(0, "a.py"), read(1, "b.py"), read(2, "a.py")]
    assert metrics.read_targets(calls) == [(0, "a.py"), (1, "b.py"), (2, "a.py")]


def test_read_targets_accepts_a_session_too():
    assert metrics.read_targets(session([read(0, "a.py")])) == [(0, "a.py")]


def test_read_targets_normalizes_windows_separators():
    assert metrics.read_targets([read(0, r"docs\plan.md")]) == [(0, "docs/plan.md")]


def test_read_targets_ignores_edits():
    assert metrics.read_targets([edit(0, "a.py"), write(1, "b.py")]) == []


def test_grep_over_a_directory_is_not_a_file_read():
    """`Grep` 의 `path` 는 디렉터리를 훑은 것일 때가 많다."""
    calls = [call(0, "Grep", {"pattern": "def", "path": "src"})]
    assert metrics.read_targets(calls) == []


def test_grep_at_one_file_is_a_file_read():
    calls = [call(0, "Grep", {"pattern": "def", "path": "src/a.py"})]
    assert metrics.read_targets(calls) == [(0, "src/a.py")]


def test_shell_cat_counts_as_reading():
    assert metrics.read_targets([shell(0, "cat docs/plan.md")]) == [(0, "docs/plan.md")]


def test_shell_head_skips_its_flags_and_counts():
    assert metrics.read_targets([shell(0, "head -n 20 a.py")]) == [(0, "a.py")]
    assert metrics.read_targets([shell(1, "head -20 a.py")]) == [(1, "a.py")]


def test_shell_read_inside_a_chain_is_found():
    calls = [shell(0, "cd repo && cat README.md")]
    assert metrics.read_targets(calls) == [(0, "README.md")]


def test_shell_that_does_not_read_contributes_nothing():
    assert metrics.read_targets([shell(0, "pytest -q")]) == []


# ------------------------------------------------------- 문서 판정


def test_document_is_decided_by_suffix_and_path():
    assert metrics.is_document("docs/v04-corrections.md")
    assert metrics.is_document("NOTES.txt")
    assert metrics.is_document("a/docs/anything.py")
    assert not metrics.is_document("src/casa/signals.py")
    assert not metrics.is_document("data/readings.csv")


def test_document_does_not_match_a_name_that_merely_contains_doc():
    """`docstore/` 는 `docs/` 가 아니다 — 경로 조각으로 맞춘다."""
    assert not metrics.is_document("docstore/index.py")


# ------------------------------------------ 서로 맞지 않는 문서 두 무리


def test_pair_coverage_reports_both_when_the_session_read_both_sides():
    calls = [read(0, "repo/HANDOFF.md"), read(1, "repo/docs/v04-corrections.md")]
    assert metrics.document_pair_coverage(
        session(calls), ["HANDOFF.md"],
        ["docs/v04-corrections.md", "docs/v05-export.md"]) == "both"


def test_pair_coverage_names_which_side_was_read():
    only_a = session([read(0, "repo/HANDOFF.md")])
    only_b = session([read(0, "repo/docs/v05-export.md")])
    neither = session([read(0, "repo/meterhouse/record.py")])
    groups = (["HANDOFF.md"], ["docs/v04-corrections.md", "docs/v05-export.md"])
    assert metrics.document_pair_coverage(only_a, *groups) == "only-a"
    assert metrics.document_pair_coverage(only_b, *groups) == "only-b"
    assert metrics.document_pair_coverage(neither, *groups) == "neither"


def test_pair_coverage_does_not_match_a_longer_name_by_accident():
    """`v04-corrections.md` 를 물었는데 `old-v04-corrections.md` 가 맞으면 안 된다."""
    calls = [read(0, "docs/old-v04-corrections.md")]
    assert metrics.document_pair_coverage(
        session(calls), ["HANDOFF.md"], ["docs/v04-corrections.md"]) == "neither"


def test_pair_coverage_treats_an_empty_group_as_unread():
    calls = [read(0, "HANDOFF.md")]
    assert metrics.document_pair_coverage(session(calls), ["HANDOFF.md"], []) == "only-a"


# --------------------------------------------------- 읽은 것의 넓이


def test_distinct_read_paths_counts_files_not_calls():
    calls = [read(0, "a.py"), read(1, "a.py"), read(2, "b.py")]
    assert signals.distinct_read_paths(calls) == 2


def test_doc_read_ratio_separates_reading_the_record_from_reading_code():
    code_only = [read(0, "a.py"), read(1, "b.py")]
    mixed = [read(0, "docs/plan.md"), read(1, "README.md"), read(2, "a.py")]
    assert signals.doc_read_ratio(code_only) == 0.0
    assert signals.doc_read_ratio(mixed) == 2 / 3


def test_doc_read_ratio_is_zero_when_nothing_was_read():
    assert signals.doc_read_ratio([shell(0, "pytest")]) == 0.0


# ----------------------------------------------------------- 차례


def test_doc_before_first_edit_is_true_when_the_record_was_read_first():
    calls = [read(0, "docs/plan.md"), edit(1, "a.py")]
    assert signals.doc_before_first_edit(calls) is True


def test_doc_before_first_edit_is_false_when_only_code_was_read_first():
    calls = [read(0, "a.py"), edit(1, "a.py"), read(2, "docs/plan.md")]
    assert signals.doc_before_first_edit(calls) is False


def test_doc_before_first_edit_is_none_when_nothing_changed():
    assert signals.doc_before_first_edit([read(0, "docs/plan.md")]) is None


def test_docs_after_first_edit_counts_going_back_to_the_record():
    calls = [read(0, "a.py"), edit(1, "a.py"),
             read(2, "docs/plan.md"), read(3, "docs/plan.md"), read(4, "b.py")]
    assert signals.docs_after_first_edit(calls) == 2


def test_docs_after_first_edit_is_zero_when_nothing_changed():
    calls = [read(0, "docs/plan.md"), read(1, "docs/other.md")]
    assert signals.docs_after_first_edit(calls) == 0


def test_first_edit_index_names_the_call_that_first_changed_a_file():
    assert signals.first_edit_index(ordinary()) == 3


def test_first_edit_index_is_none_when_nothing_changed():
    assert signals.first_edit_index([read(0, "a.py"), shell(1, "pytest")]) is None


def test_first_edit_index_counts_a_mutating_shell_command():
    calls = [read(0, "a.py"), shell(1, "git checkout -- a.py")]
    assert signals.first_edit_index(calls) == 1


def test_max_reread_gap_measures_how_much_later_the_session_came_back():
    calls = [read(0, "a.py")] + [shell(i, "pytest") for i in range(1, 9)] \
        + [read(9, "a.py")]
    assert signals.max_reread_gap(calls) == 9


def test_max_reread_gap_is_zero_without_a_second_read():
    assert signals.max_reread_gap([read(0, "a.py"), read(1, "b.py")]) == 0


def test_max_reread_gap_takes_the_widest_of_several():
    calls = [read(0, "a.py"), read(1, "b.py"), read(3, "b.py"), read(8, "a.py")]
    assert signals.max_reread_gap(calls) == 8


def test_read_before_edit_ratio_is_one_when_every_change_was_looked_at_first():
    assert signals.read_before_edit_ratio(ordinary()) == 1.0


def test_read_before_edit_ratio_drops_when_a_file_is_changed_unseen():
    calls = [read(0, "a.py"), edit(1, "a.py"), write(2, "b.py")]
    assert signals.read_before_edit_ratio(calls) == 0.5


def test_reading_a_file_only_after_changing_it_does_not_count():
    calls = [edit(0, "a.py"), read(1, "a.py")]
    assert signals.read_before_edit_ratio(calls) == 0.0


def test_read_before_edit_ratio_is_none_when_nothing_changed():
    assert signals.read_before_edit_ratio([read(0, "a.py")]) is None


# ------------------------------------------------------- 조용한가


def test_the_new_signals_stay_quiet_on_an_ordinary_session():
    """모든 세션에서 값이 오르는 지표는 읽는 사람의 주의만 쓴다."""
    out = signals.compute_signals(session(ordinary()))
    assert out["distinct_read_paths"] == 3
    assert out["doc_read_ratio"] == 0.0
    assert out["doc_before_first_edit"] is False
    assert out["docs_after_first_edit"] == 0
    assert out["max_reread_gap"] == 0
    assert out["read_before_edit_ratio"] == 1.0


def test_the_battery_carries_the_new_signals():
    out = signals.compute_signals(session(ordinary()))
    for key in ("distinct_read_paths", "doc_read_ratio", "doc_before_first_edit",
                "docs_after_first_edit", "max_reread_gap",
                "read_before_edit_ratio"):
        assert key in out


def test_the_new_signals_never_look_at_the_final_message():
    """마지막 메시지에서 계산하면 정답이 새어 든다 — `assertion_density` 가
    그래서 초반 신호 탐색에서 빠졌다. 이 여섯은 도구 호출만 본다."""
    with_text = session(ordinary())
    with_text.final_assistant_text = "All done, everything passes."
    without = session(ordinary())
    keys = ("distinct_read_paths", "doc_read_ratio", "doc_before_first_edit",
            "docs_after_first_edit", "max_reread_gap", "read_before_edit_ratio")
    a, b = signals.compute_signals(with_text), signals.compute_signals(without)
    assert [a[k] for k in keys] == [b[k] for k in keys]
