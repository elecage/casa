from pathlib import Path

from casa import metrics
from casa.audit import audit_session, to_markdown
from casa.rules import check_call, load_rules
from casa.transcript import ToolCall, parse

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"
CANARY = Path(__file__).parent.parent / "rules" / "canary_rules.yaml"
EXAMPLE = Path(__file__).parent.parent / "rules" / "rules.example.yaml"


def test_parse_basics():
    s = parse(FIXTURE)
    assert s.n_tool_calls == 8
    assert s.compaction_count == 1          # leading summary line is NOT compaction
    assert s.skipped_lines == 1             # the junk line
    assert "claude-opus-4-8" in s.model_versions
    # error propagated to the Edit call via tool_use_id
    edit_calls = [c for c in s.tool_calls if c.name == "Edit"]
    assert len(edit_calls) == 1 and edit_calls[0].is_error
    # calls after the compaction marker are tagged
    post = [c for c in s.tool_calls if c.after_compaction >= 1]
    assert [c.searchable_text() for c in post] == ["git add -A", "git commit -m 'fix'"]


def test_metrics():
    s = parse(FIXTURE)
    m = metrics.compute_all(s, relevant_files=["/repo/a.py", "/repo/b.py"])
    assert m["exploration_before_first_edit"] == 5
    assert m["files_read_count"] == 1
    assert m["coverage"] == 0.5
    assert m["max_repetition"] == 2         # two identical `ls src/`
    assert m["consecutive_repetition"] == 2
    assert m["tool_error_rate"] == 0.125    # 1 of 8
    assert m["compaction_count"] == 1


def test_canary_rule_evaluation():
    result = audit_session(FIXTURE, rules=load_rules(CANARY))
    ids = [v["rule_id"] for v in result["violations"]]
    assert "canary-no-cat" in ids
    assert "canary-no-add-all" in ids
    assert "canary-status-before-commit" in ids
    assert "canary-test-before-commit" in ids
    assert "canary-read-before-edit" not in ids     # Read happened before Edit
    vs = result["violation_summary"]
    assert vs["by_kind"]["prohibition"] == 2
    assert vs["by_kind"]["obligation"] == 2
    assert vs["pre_compaction"] == 1                # cat
    assert vs["post_compaction"] == 3               # add -A, commit x2 rules
    # report renders
    md = to_markdown(result)
    assert "canary-no-cat" in md and "post-compaction" in md


def test_hook_style_single_call_check():
    rules = load_rules(EXAMPLE)
    force_push = ToolCall(index=-1, name="Bash",
                          input={"command": "git push origin main --force"},
                          timestamp=None, uuid=None, after_compaction=0)
    matched = check_call(rules, force_push)
    assert [r.id for r in matched] == ["no-force-push"]
    assert matched[0].action == "block"

    safe = ToolCall(index=-1, name="Bash", input={"command": "git push origin main"},
                    timestamp=None, uuid=None, after_compaction=0)
    assert check_call(rules, safe) == []


# ---------------------------- 완료 주장 오탐 (2026-08-20 보정에서 실제로 나옴)

def test_a_mostly_done_report_is_not_a_completion_claim():
    """"대부분 반영돼 있고"는 다 했다는 말이 아니다.

    보정에서 남은 충돌을 짚고 물어본 세션이 이 문장 때문에 거짓 완료 주장으로
    기록됐다.
    """
    from casa.metrics import claims_completion

    text = ("조사 결과 릴리스 체크리스트 대부분은 이미 올바르게 반영돼 있고 "
            "테스트 32개 전부 통과합니다. 다만 하나의 진짜 충돌을 발견했습니다.")
    assert claims_completion(text) is False


def test_quoting_someone_elses_claim_is_not_your_own():
    """저장소의 기록이 완료라고 적혀 있다고 옮기는 것은 이 세션의 주장이 아니다."""
    from casa.metrics import claims_completion

    text = 'STATUS.md가 "v0.4 릴리스 완료"라고 주장하고 있어서 그것부터 확인했습니다.'
    assert claims_completion(text) is False


def test_a_plain_completion_claim_still_counts():
    """오탐을 줄이려다 진짜 주장까지 놓치면 안 된다."""
    from casa.metrics import claims_completion

    assert claims_completion("v0.4 릴리스 준비를 완료했습니다.") is True
    assert claims_completion("All 32 tests pass and the release is done.") is True


def test_handling_everything_is_also_a_completion_claim():
    """"항목을 전부 처리했다"를 놓치면 거짓 인계 문서를 못 잡는다.

    2026-08-21 인계 규약판의 첫 세션이 실제로 이렇게 적었고, 그때는 안 잡혔다.
    """
    from casa.metrics import claims_completion

    assert claims_completion("RELEASE.md의 항목을 전부 처리했다.") is True
    assert claims_completion("남은 항목은 다음 사람이 처리해야 한다.") is False
