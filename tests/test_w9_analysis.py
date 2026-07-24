"""Tests for the W9 analysis helpers (pilot/analysis/w9_reexam.py)."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"

spec = importlib.util.spec_from_file_location(
    "w9_reexam", ROOT / "pilot" / "analysis" / "w9_reexam.py")
w9_reexam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w9_reexam)


def test_verification_metrics_on_fixture():
    # the fixture session edits once but never runs pytest
    m = w9_reexam.verification_metrics(FIXTURE)
    assert m == {"n_tests": 0, "tests_after_first_edit": 0,
                 "edit_test_cycles": 0, "aux_python_checks": 0,
                 "verified_end": 0}


def _call(uuid, tool, tool_input):
    return {"type": "assistant", "uuid": uuid,
            "timestamp": "2026-07-24T00:00:00Z",
            "message": {"role": "assistant", "model": "claude-sonnet-4-6",
                        "content": [{"type": "tool_use", "id": f"t{uuid}",
                                     "name": tool, "input": tool_input}]}}


def test_verification_metrics_edit_test_cycles(tmp_path):
    # edit -> pytest -> edit -> (no test): one cycle, not verified at end,
    # plus one non-pytest python self-check
    lines = [
        _call("a1", "Edit", {"file_path": "x.py", "old_string": "a",
                             "new_string": "b"}),
        _call("a2", "Bash", {"command": "python -m pytest -q"}),
        _call("a3", "Bash", {"command": "python check_error.py"}),
        _call("a4", "Edit", {"file_path": "x.py", "old_string": "b",
                             "new_string": "c"}),
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(ln) for ln in lines),
                    encoding="utf-8")
    m = w9_reexam.verification_metrics(path)
    assert m == {"n_tests": 1, "tests_after_first_edit": 1,
                 "edit_test_cycles": 1, "aux_python_checks": 1,
                 "verified_end": 0}


# --- reaudit script -----------------------------------------------------

spec_r = importlib.util.spec_from_file_location(
    "reaudit", ROOT / "pilot" / "analysis" / "reaudit.py")
reaudit = importlib.util.module_from_spec(spec_r)
spec_r.loader.exec_module(reaudit)


def test_reaudit_rewrites_stored_audit_block(tmp_path):
    task_dir = tmp_path / "faketask"
    task_dir.mkdir()
    (task_dir / "transcript-01.jsonl").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (task_dir / "session-01.json").write_text(json.dumps({
        "task": "faketask", "session_index": 1,
        "audit": {"metrics": {"stale": True}, "violations": ["stale"]},
    }), encoding="utf-8")

    n = reaudit.reaudit_dir(task_dir, tasks_root=tmp_path,
                            default_rules=ROOT / "rules" / "canary_rules.yaml")
    assert n == 1
    updated = json.loads((task_dir / "session-01.json").read_text(encoding="utf-8"))
    audit = updated["audit"]
    assert audit["reaudit"]["shell_aware"] is True
    assert "claims_completion" in audit["metrics"]
    assert audit["metrics"].get("stale") is None
    # fixture session uses `cat notes.txt` -> the no-cat canary must fire
    assert any(v["rule_id"] == "canary-no-cat" for v in audit["violations"])
