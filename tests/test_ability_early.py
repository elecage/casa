"""Tests for the ability-axis early-detection analysis.

The three properties worth pinning are the ones that were actually wrong
during development, each of which changed the conclusion:

1. token accounting must count one assistant message once. Transcripts
   repeat a message per content block with the same usage record, and the
   naive sum inflated one orbit session to 43131 output tokens against the
   CLI's own 15906 -- which made early spend look ~3x larger than it is.
2. the restart simulation must include sessions that end before step k
   (they simply cannot be flagged). Dropping them prices the policy on
   long sessions only, which flatters it.
3. the kill-everything null must be computable, because in a condition
   where almost nothing succeeds, stopping early and re-rolling improves
   tokens-per-success on arithmetic alone.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot" / "analysis"))

import ability_early as ae  # noqa: E402


# --- helpers ------------------------------------------------------------


def _assistant(msg_id: str, out_tokens: int, blocks: list[dict]) -> str:
    return json.dumps({"type": "assistant",
                       "message": {"id": msg_id,
                                   "usage": {"output_tokens": out_tokens},
                                   "content": blocks}})


def _tool_use(name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "name": name, "input": tool_input,
            "id": f"tu_{name}_{len(json.dumps(tool_input))}"}


def _write(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- token accounting ---------------------------------------------------


def test_token_prefix_counts_each_message_once(tmp_path):
    """The same message repeated per content block must not be summed twice."""
    text_block = {"type": "text", "text": "thinking"}
    call = _tool_use("Read", {"file_path": "a.py"})
    lines = [
        _assistant("msg_1", 100, [text_block]),
        _assistant("msg_1", 100, [call]),          # same message, second block
        _assistant("msg_2", 50, [_tool_use("Read", {"file_path": "b.py"})]),
    ]
    assert ae.token_prefix(_write(tmp_path, lines)) == [100, 150]


def test_token_prefix_without_ids_counts_each_record(tmp_path):
    """Tolerant fallback: no message id means no dedup information."""
    line = json.dumps({"type": "assistant",
                       "message": {"usage": {"output_tokens": 7},
                                   "content": [_tool_use("Read", {"file_path": "a.py"})]}})
    assert ae.token_prefix(_write(tmp_path, [line, line])) == [7, 14]


def test_token_prefix_skips_unparsable_and_non_assistant(tmp_path):
    lines = ["{not json", json.dumps({"type": "user", "message": {}}),
             _assistant("m", 5, [_tool_use("Read", {"file_path": "a.py"})])]
    assert ae.token_prefix(_write(tmp_path, lines)) == [5]


# --- prefix features ----------------------------------------------------


def _session(tmp_path, n_reads: int, repeat_same: bool = False):
    from casa.transcript import parse
    lines = []
    for i in range(n_reads):
        target = "same.py" if repeat_same else f"f{i}.py"
        lines.append(_assistant(f"m{i}", 10, [_tool_use("Read", {"file_path": target})]))
    path = _write(tmp_path, lines)
    return parse(path), ae.token_prefix(path)


def test_features_at_returns_none_before_step_k(tmp_path):
    session, tokens = _session(tmp_path, n_reads=3)
    assert ae.features_at(session, tokens, [], None, 8) is None
    assert ae.features_at(session, tokens, [], None, 2) is not None


def test_features_at_counts_prefix_only(tmp_path):
    session, tokens = _session(tmp_path, n_reads=6)
    at4 = ae.features_at(session, tokens, [], ["f0.py", "f1.py", "f9.py"], 4)
    assert at4["files_read"] == 4
    assert at4["out_tokens"] == 40           # 4 messages x 10 tokens
    assert at4["coverage"] == pytest.approx(2 / 3)
    assert at4["repetition"] == 1
    assert at4["mutated"] == 0.0


def test_features_at_detects_repetition(tmp_path):
    session, tokens = _session(tmp_path, n_reads=4, repeat_same=True)
    assert ae.features_at(session, tokens, [], None, 4)["repetition"] == 4


def test_features_at_counts_only_earlier_violations(tmp_path):
    session, tokens = _session(tmp_path, n_reads=6)
    violations = [{"call_index": 0}, {"call_index": 3}, {"call_index": 5}]
    assert ae.features_at(session, tokens, violations, None, 2)["violations"] == 1
    assert ae.features_at(session, tokens, violations, None, 4)["violations"] == 2


# --- targets ------------------------------------------------------------


def _row(index: int, tokens: int, success: bool, claims: bool = True,
         at_k: dict | None = None) -> dict:
    prefix = {k: None for k in ae.KS}
    if at_k:
        for k, feats in at_k.items():
            prefix[k] = feats
    return {"index": index, "success": success, "claims": claims,
            "final_tokens": tokens, "n_calls": 20, "prefix": prefix}


def test_label_expensive_marks_top_quartile():
    rows = [_row(i, tokens, True) for i, tokens in
            enumerate([100, 200, 300, 400, 500, 600, 700, 800])]
    labels = ae.label_expensive(rows)
    assert labels[-1] is True and labels[-2] is True      # 800, 700
    assert labels[0] is False


def test_label_false_done_needs_claim_and_failure():
    rows = [_row(0, 10, success=False, claims=True),
            _row(1, 10, success=False, claims=False),
            _row(2, 10, success=True, claims=True)]
    assert ae.label_false_done(rows) == [True, False, False]


# --- policies -----------------------------------------------------------


def _policy_rows():
    """9 sessions; only the four long failing ones reach step 2."""
    rows = [_row(i, 1000, success=(i < 3)) for i in range(5)]   # never scorable
    for offset, (tokens, errors) in enumerate(
            [(9000, 4.0), (8000, 3.0), (7000, 3.0), (6000, 2.0)]):
        rows.append(_row(5 + offset, tokens, success=False,
                         at_k={2: {"out_tokens": 500.0, "errors": errors}}))
    return rows


def test_restart_policy_keeps_sessions_that_never_reach_k():
    rows = _policy_rows()
    got = ae.restart_policy(rows, ae.label_expensive(rows), 2, "errors")
    assert got is not None
    assert got["n"] == 9            # all nine priced, not just the scorable four
    assert got["n_scorable"] == 4
    # baseline: 35000 tokens spent for 3 successes
    assert got["baseline_tokens_per_success"] == pytest.approx(35000 / 3)


def test_restart_policy_flags_only_above_threshold():
    rows = _policy_rows()
    got = ae.restart_policy(rows, ae.label_expensive(rows), 2, "errors")
    # only the four failing long sessions can be killed
    assert got["killed"] <= 4
    assert got["successes_killed"] == 0


def test_restart_policy_refuses_too_few_scorable_sessions():
    """A threshold fitted on one or two points is not a policy."""
    rows = [_row(i, 1000, success=(i < 3)) for i in range(7)]
    rows.append(_row(7, 9000, success=False,
                     at_k={2: {"out_tokens": 500.0, "errors": 4.0}}))
    assert ae.restart_policy(rows, ae.label_expensive(rows), 2, "errors") is None


def test_kill_all_policy_kills_every_scorable_session():
    rows = _policy_rows()
    got = ae.kill_all_policy(rows, 2)
    assert got["killed"] == 4
    assert got["tokens_per_success"] > 0


def test_kill_all_policy_needs_a_success():
    rows = [_row(i, 1000, success=False) for i in range(8)]
    assert ae.kill_all_policy(rows, 2) is None


def test_waste_accounting_splits_by_eventual_outcome():
    rows = [_row(0, 1000, success=False, at_k={8: {"out_tokens": 400.0}}),
            _row(1, 1000, success=True, at_k={8: {"out_tokens": 900.0}})]
    got = ae.waste_accounting(rows, k=8)
    assert got["recoverable"] == 600         # failing session, after step 8
    assert got["at_risk"] == 100             # successful session, after step 8
    assert got["recoverable_pct"] == pytest.approx(30.0)


def test_waste_accounting_treats_short_sessions_as_unrecoverable():
    """A session that ended before step k has nothing left to cut."""
    rows = [_row(0, 1000, success=False)]
    got = ae.waste_accounting(rows, k=8)
    assert got["recoverable"] == 0


# --- discrimination -----------------------------------------------------


def test_discrimination_reports_perfect_separation():
    rows = [_row(i, 100 * (i + 1), success=True,
                 at_k={2: {"out_tokens": float(i)}}) for i in range(8)]
    labels = ae.label_expensive(rows)
    table = ae.discrimination(rows, labels)
    assert table["out_tokens"][2] == pytest.approx(1.0)


def test_sample_at_reports_shrinking_subsample():
    rows = [_row(0, 100, True, at_k={2: {"out_tokens": 1.0}}),
            _row(1, 200, True)]
    positives, total = ae.sample_at(rows, [True, False], 2)
    assert (positives, total) == (1, 1)
