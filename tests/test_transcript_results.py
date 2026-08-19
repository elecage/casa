"""Tests for tool-result capture in the transcript parser.

Progress judgement (docs/PROGRESS_RULE.md) asks whether a call produced
anything new, and that cannot be answered from the call's input: two identical
`pytest` invocations differ only in what they printed. The parser previously
took one bit (is_error) from each result and discarded the body, so these
tests pin the capture.

Each test below fixes a property that would silently corrupt progress
judgement if it broke:

1. both observed body shapes must be read (a plain string, and a list of
   content blocks) — missing one shape would make those calls look
   result-less, i.e. indistinguishable from each other.
2. the hash must be taken before truncation, or two long outputs sharing a
   prefix would collide and a repeated failing test would look like progress.
3. a call with no matching result must stay distinguishable from a call whose
   result was an empty string.
4. unknown shapes must yield None rather than raise — the format is
   undocumented and version-dependent (ARCHITECTURE principle 2).
"""

import hashlib
import json
from pathlib import Path

from casa.transcript import MAX_RESULT_CHARS, parse

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "session.jsonl"
    p.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return p


def _call(tool_use_id: str, name: str = "Bash", command: str = "pytest") -> dict:
    return {
        "type": "assistant",
        "timestamp": "2026-08-19T00:00:00Z",
        "message": {
            "model": "claude-test",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": {"command": command},
                }
            ],
        },
    }


def _result(tool_use_id: str, content, is_error: bool = False) -> dict:
    item = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        item["is_error"] = True
    return {
        "type": "user",
        "timestamp": "2026-08-19T00:00:01Z",
        "message": {"content": [item]},
    }


# ------------------------------------------------------------- body shapes


def test_string_body_is_captured(tmp_path):
    body = "3 failed, 5 passed"
    s = parse(_write(tmp_path, [_call("t1"), _result("t1", body)]))
    call = s.tool_calls[0]
    assert call.result_text == body
    assert call.result_len == len(body)
    assert call.result_hash == hashlib.sha256(body.encode()).hexdigest()
    assert call.result_truncated is False
    assert call.has_result is True


def test_block_list_body_is_joined(tmp_path):
    content = [
        {"type": "text", "text": "first"},
        {"type": "image", "source": {}},
        {"type": "text", "text": "second"},
    ]
    s = parse(_write(tmp_path, [_call("t1"), _result("t1", content)]))
    assert s.tool_calls[0].result_text == "first\nsecond"


def test_error_result_keeps_flag_and_body(tmp_path):
    s = parse(_write(tmp_path, [_call("t1"), _result("t1", "boom", is_error=True)]))
    call = s.tool_calls[0]
    assert call.is_error is True
    assert call.result_text == "boom"


# ------------------------------------------------------- identity, not shape


def test_hash_is_taken_before_truncation(tmp_path):
    """Two long outputs sharing a prefix must not collide.

    Otherwise a test that keeps failing with a slightly different tail would
    read as 'the evidence changed' — the exact signal the progress rule needs.
    """
    prefix = "x" * 50
    a, b = prefix + "aaa", prefix + "bbb"
    entries = [_call("t1"), _result("t1", a), _call("t2"), _result("t2", b)]
    s = parse(_write(tmp_path, entries), max_result_chars=len(prefix))
    first, second = s.tool_calls[0], s.tool_calls[1]

    assert first.result_truncated and second.result_truncated
    assert first.result_text == second.result_text == prefix  # truncated alike
    assert first.result_hash != second.result_hash            # but distinguishable
    assert first.result_len == len(a)


def test_identical_bodies_share_a_hash(tmp_path):
    entries = [_call("t1"), _result("t1", "same"), _call("t2"), _result("t2", "same")]
    s = parse(_write(tmp_path, entries))
    assert s.tool_calls[0].result_hash == s.tool_calls[1].result_hash


def test_default_cap_leaves_ordinary_output_whole(tmp_path):
    body = "line\n" * 1000
    assert len(body) < MAX_RESULT_CHARS
    s = parse(_write(tmp_path, [_call("t1"), _result("t1", body)]))
    assert s.tool_calls[0].result_truncated is False


# ------------------------------------------------------------- missing/odd


def test_call_without_result_is_distinguishable_from_empty_result(tmp_path):
    entries = [_call("t1"), _call("t2"), _result("t2", "")]
    s = parse(_write(tmp_path, entries))
    missing, empty = s.tool_calls[0], s.tool_calls[1]

    assert missing.has_result is False
    assert missing.result_hash is None and missing.result_len == 0
    assert empty.has_result is True
    assert empty.result_text == "" and empty.result_len == 0


def test_unknown_body_shapes_do_not_raise(tmp_path):
    entries = [
        _call("t1"), _result("t1", {"unexpected": "dict"}),
        _call("t2"), _result("t2", [{"type": "image", "source": {}}]),
        _call("t3"), _result("t3", None),
    ]
    s = parse(_write(tmp_path, entries))
    assert [c.has_result for c in s.tool_calls] == [False, False, False]
    assert s.skipped_lines == 0


def test_result_for_unknown_call_is_ignored(tmp_path):
    s = parse(_write(tmp_path, [_call("t1"), _result("nope", "orphan")]))
    assert s.tool_calls[0].has_result is False


# ------------------------------------------------------------- real data


def test_fixture_results_are_captured():
    """The shipped fixture has 8 calls, each with a result."""
    s = parse(FIXTURE)
    assert len(s.tool_calls) == 8
    assert all(c.has_result for c in s.tool_calls)
    assert all(c.result_hash and c.result_len >= 0 for c in s.tool_calls)
