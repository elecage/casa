"""Session-independence check — evidence that within-condition variability
is genuine, not a cross-session leakage / convergence artefact.

Defends a threat to validity (docs/RESEARCH_PLAN.md "리스크와 방어"): the
runner gives each session a fresh template copy, its own git repo, and a
distinct transcript project dir, and there is no shared user-level memory —
so sessions cannot influence one another. This module supplies the
*behavioral* evidence for the same claim via two order-effect tests over a
batch of session JSONs:

- success rate by index thirds — a "learns as it repeats" convergence would
  show a monotone rise across thirds;
- trajectory similarity for temporally adjacent vs distant session pairs —
  leakage would make adjacent (close-in-time) sessions more similar than
  distant ones.

Deterministic, stdlib + casa only.

    .venv/Scripts/python.exe pilot/analysis/session_independence.py \
        results/main2/orbit-sonnet
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

from casa.metrics import normalized_edit_distance, tool_sequence  # noqa: E402
from casa.transcript import parse  # noqa: E402


def success_by_bins(items: list[tuple[int, bool]],
                    bins: int = 3) -> list[tuple[int, int]]:
    """Split (session_index, success) rows into `bins` contiguous groups by
    index order and return (successes, total) per bin. A convergence trend
    shows as a monotone rise in the success fraction across bins."""
    ordered = [s for _, s in sorted(items)]
    n = len(ordered)
    if n == 0:
        return []
    size = max(1, n // bins)
    out: list[tuple[int, int]] = []
    for b in range(bins):
        lo = b * size
        hi = n if b == bins - 1 else (b + 1) * size
        chunk = ordered[lo:hi]
        if chunk:
            out.append((sum(1 for s in chunk if s), len(chunk)))
    return out


def similarity_by_distance(seqs: dict[int, list[str]],
                           near: int = 1, far: int = 10) -> dict:
    """Mean trajectory similarity (1 - normalized edit distance) for session
    pairs that are adjacent in index (distance == near) vs distant
    (distance >= far). Leakage would make `adjacent` exceed `distant`."""
    idx = sorted(seqs)
    adjacent: list[float] = []
    distant: list[float] = []
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            gap = idx[j] - idx[i]
            sim = 1.0 - normalized_edit_distance(seqs[idx[i]], seqs[idx[j]])
            if gap == near:
                adjacent.append(sim)
            elif gap >= far:
                distant.append(sim)
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    a, d = mean(adjacent), mean(distant)
    return {
        "adjacent_mean": a, "adjacent_n": len(adjacent),
        "distant_mean": d, "distant_n": len(distant),
        "delta": round(a - d, 4) if a is not None and d is not None else None,
    }


def load_batch(results_dir: Path) -> tuple[list[tuple[int, bool]], dict[int, list[str]]]:
    items: list[tuple[int, bool]] = []
    seqs: dict[int, list[str]] = {}
    for jf in sorted(glob.glob(str(results_dir / "session-*.json"))):
        d = json.load(open(jf, encoding="utf-8"))
        idx = d.get("session_index")
        items.append((idx, bool(d.get("grade", {}).get("success"))))
        tp = d.get("transcript")
        if tp and Path(tp).exists():
            seqs[idx] = tool_sequence(parse(tp))
    return items, seqs


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: session_independence.py <results_dir>", file=sys.stderr)
        return 2
    results_dir = Path(sys.argv[1]).resolve()
    items, seqs = load_batch(results_dir)
    print(f"batch: {results_dir.name}  (n={len(items)})")
    bins = success_by_bins(items)
    labels = ["early", "middle", "late"][:len(bins)]
    print("success rate by index thirds (convergence would rise):")
    for name, (s, tot) in zip(labels, bins):
        print(f"  {name:6s}: {s}/{tot} ({100*s/tot:.0f}%)")
    sim = similarity_by_distance(seqs)
    print("trajectory similarity (leakage would make adjacent > distant):")
    print(f"  adjacent (gap=1):  {sim['adjacent_mean']}  (n={sim['adjacent_n']})")
    print(f"  distant  (gap>=10): {sim['distant_mean']}  (n={sim['distant_n']})")
    print(f"  delta (adjacent - distant): {sim['delta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
