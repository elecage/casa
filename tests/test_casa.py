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
