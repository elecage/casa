"""Signal validation on collected batches — does any deterministic
behavioral signal separate *true* completions (claimed done and passed the
hidden oracle) from *false* completions (claimed done but failed it)?

Backs docs/W13_FINDINGS.md. Two views over a results dir of session JSONs:

- completion AUROC: among sessions that CLAIM completion, how well each
  verification metric ranks true above false completions;
- cost spread: max/min total_cost_usd among successful sessions (effort
  variance that pass/fail hides).

Deterministic, stdlib only.

    .venv/Scripts/python.exe pilot/analysis/signal_validation.py \
        results/main2/orbit-sonnet results/main2/layered-ledger-haiku
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

METRICS = ["n_test_runs", "edit_test_cycles", "verified_end", "aux_python_checks"]


def _metric(row: dict, key: str):
    return row.get("audit", {}).get("metrics", {}).get(key)


def _success(row: dict) -> bool:
    return bool(row.get("grade", {}).get("success"))


def _claims(row: dict) -> bool:
    return bool(_metric(row, "claims_completion"))


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """Probability a random positive ranks above a random negative (ties
    count 0.5). None if either group is empty."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def completion_split(rows: list[dict], key: str) -> tuple[list, list]:
    """(values on true completions, values on false completions), taken over
    sessions that claim completion and have a numeric value for `key`."""
    claim = [r for r in rows if _claims(r)]
    true_vals, false_vals = [], []
    for r in claim:
        v = _metric(r, key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            (true_vals if _success(r) else false_vals).append(v)
    return true_vals, false_vals


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x: list, y: list, min_n: int = 4) -> float | None:
    """Spearman rank correlation over index-aligned numeric pairs (non-numeric
    pairs dropped). None if fewer than `min_n` usable pairs or no variance."""
    pts = [(a, b) for a, b in zip(x, y)
           if isinstance(a, (int, float)) and not isinstance(a, bool)
           and isinstance(b, (int, float)) and not isinstance(b, bool)]
    if len(pts) < min_n:
        return None
    rx, ry = _rank([p[0] for p in pts]), _rank([p[1] for p in pts])
    n = len(pts)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n))
           * sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return round(num / den, 3) if den else None


def outcome_series(rows: list[dict], outcome: str) -> list:
    """Per-session outcome facet as a numeric series: 'success' (0/1),
    'cost' (total_cost_usd), or 'violations' (count)."""
    out = []
    for r in rows:
        if outcome == "success":
            out.append(1 if _success(r) else 0)
        elif outcome == "cost":
            out.append(r.get("cli", {}).get("total_cost_usd"))
        elif outcome == "violations":
            out.append(len(r.get("audit", {}).get("violations", []) or []))
        else:
            out.append(_metric(r, outcome))
    return out


def cost_spread(rows: list[dict]) -> dict | None:
    """min/max/ratio of total_cost_usd over successful sessions."""
    costs = [r.get("cli", {}).get("total_cost_usd") for r in rows if _success(r)]
    costs = [c for c in costs if isinstance(c, (int, float))]
    if len(costs) < 2:
        return None
    return {"n": len(costs), "min": round(min(costs), 4),
            "max": round(max(costs), 4),
            "ratio": round(max(costs) / min(costs), 2) if min(costs) else None}


def load(results_dir: Path) -> list[dict]:
    return [json.load(open(f, encoding="utf-8"))
            for f in sorted(glob.glob(str(results_dir / "session-*.json")))]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: signal_validation.py <results_dir> [<results_dir> ...]",
              file=sys.stderr)
        return 2
    for arg in sys.argv[1:]:
        rows = load(Path(arg).resolve())
        claim = [r for r in rows if _claims(r)]
        t = sum(1 for r in claim if _success(r))
        print(f"\n{Path(arg).name}: n={len(rows)}, claim-done={len(claim)} "
              f"(true={t}, false={len(claim)-t})")
        for key in METRICS:
            tv, fv = completion_split(rows, key)
            a = auroc(tv, fv)
            if a is not None:
                print(f"  {key:20s} AUROC={a}")
        sp = cost_spread(rows)
        if sp:
            print(f"  cost spread (successes): x{sp['ratio']} "
                  f"(${sp['min']}-${sp['max']}, n={sp['n']})")
        # multi-dimensional structure: metric vs each user-felt outcome
        corr_metrics = ["coverage", "exploration_before_first_edit",
                        "n_test_runs", "aux_python_checks", "max_repetition",
                        "n_tool_calls"]
        print(f"  {'metric':30s} {'~success':>9} {'~cost':>7} {'~violations':>11}")
        for key in corr_metrics:
            col = [_metric(r, key) for r in rows]
            row_out = [spearman(col, outcome_series(rows, o))
                       for o in ("success", "cost", "violations")]
            print(f"  {key:30s} " + " ".join(f"{str(v):>9}" for v in row_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
