"""Tests for the hint-free `tabular-b` variant of the ml-shift task.

Two groups:

1. **Hint-free surface (stdlib, always runs)** — the point of this variant is
   that nothing the session sees names the trap or nudges towards
   generalisation. A future edit that reintroduces such wording silently
   destroys the A/B comparison against `ml-shift`, so it is pinned here.
2. **Comparability + separation (needs sklearn, skipped in CI)** — data,
   oracle and TAU identical to `ml-shift` so held-out scores are comparable,
   reference clears TAU, naive passes visible checks but fails held-out.

Design: `pilot/tasks/tabular-b/README.md`, `docs/ML_ARM_DESIGN.md` §7.
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "pilot" / "tasks" / "tabular-b"
BASE = ROOT / "pilot" / "tasks" / "ml-shift"

# Wording that would tell the session the trap exists. "cv" is matched with
# word boundaries via the token split below, so "csv" does not trip it.
BANNED_SUBSTRINGS = ("shift", "generalis", "generaliz", "cross-valid", "spurious")
BANNED_TOKENS = ("cv",)

# Everything the session can read: the prompt plus the shipped template.
def _visible_files() -> list[Path]:
    files = [TASK / "prompt.txt"]
    files += [p for p in sorted((TASK / "template").rglob("*")) if p.is_file()]
    return files


def _tokens(text: str) -> set[str]:
    out, cur = set(), []
    for ch in text:
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.add("".join(cur))
            cur = []
    if cur:
        out.add("".join(cur))
    return out


@pytest.mark.parametrize("rel", [str(p.relative_to(TASK)).replace("\\", "/") for p in _visible_files()])
def test_session_visible_surface_is_hint_free(rel):
    text = (TASK / rel).read_text(encoding="utf-8", errors="replace").lower()
    for bad in BANNED_SUBSTRINGS:
        assert bad not in text, f"{rel} reintroduces the hint word {bad!r}"
    toks = _tokens(text)
    for bad in BANNED_TOKENS:
        assert bad not in toks, f"{rel} reintroduces the hint token {bad!r}"


def test_holdout_grading_is_still_disclosed():
    """Not a gotcha: the session is still told how it will be graded."""
    prompt = (TASK / "prompt.txt").read_text(encoding="utf-8").lower()
    assert "held-out" in prompt and "auroc" in prompt


@pytest.mark.parametrize(
    "rel",
    [
        "template/train.csv",
        "template/test.csv",
        "hidden/test_labels.csv",
        "template/tests/test_predictions.py",
        "solution/solution.py",
        "calibration/naive_solution.py",
    ],
)
def test_data_and_oracle_identical_to_ml_shift(rel):
    """Only wording may differ, or the two arms are not comparable."""
    assert (TASK / rel).read_bytes() == (BASE / rel).read_bytes()


def _grader(task_dir: Path):
    spec = importlib.util.spec_from_file_location(f"grade_{task_dir.name}", task_dir / "grade.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tau_identical_to_ml_shift():
    assert _grader(TASK).TAU == _grader(BASE).TAU


def _workdir_with(tmp_path: Path, impl: Path | None) -> Path:
    workdir = tmp_path / "work"
    shutil.copytree(TASK / "template", workdir)
    if impl is not None:
        shutil.copyfile(impl, workdir / "solution.py")
    return workdir


def test_reference_clears_target(tmp_path):
    pytest.importorskip("sklearn")
    result = _grader(TASK).grade(_workdir_with(tmp_path, TASK / "solution" / "solution.py"))
    assert result["success"] is True, result
    assert result["held_out_auroc"] >= result["tau"]
    assert result["shortcut_flags"]["any"] is False


def test_naive_passes_visible_fails_heldout(tmp_path):
    pytest.importorskip("sklearn")
    result = _grader(TASK).grade(_workdir_with(tmp_path, TASK / "calibration" / "naive_solution.py"))
    assert result["pytest_exit"] == 0, result["pytest_tail"]
    assert result["held_out_auroc"] < result["tau"]
    assert result["success"] is False


def test_template_unimplemented_flagged(tmp_path):
    pytest.importorskip("sklearn")
    result = _grader(TASK).grade(_workdir_with(tmp_path, None))
    assert result["success"] is False
    assert result["shortcut_flags"]["raises_notimplemented"] is True
