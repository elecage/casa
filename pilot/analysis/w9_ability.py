"""W9 addendum: session ABILITY variance (docs/PILOT_RESULTS.md section 8).

The user's core question is not pass/fail but session-level working ability:
"opening a new session on the same project seems to draw a different level of
competence each time — can that be detected early to save time and tokens?"

This script measures exactly that on the pilot data, with content/token
signals only (no wall-clock, per the 2026-07-24 decision):

(1) efficiency spread among SAME-OUTCOME sessions of the identical task
    (turns / output tokens / cost to finish) — ability variance beyond
    the success bit
(2) whether final session size is visible early (Spearman between
    exploration features at call k and final output tokens, successes only)
(3) the token value of a hypothetical early-stop-and-restart policy on the
    one task with many failures (orbit-propagator)

Requires local results/main/ (not in git); run from the repo root:

    .venv/Scripts/python.exe pilot/analysis/w9_ability.py [results/main]
"""

from __future__ import annotations

import sys
from pathlib import Path

from casa.report import load_sessions, spearman

TASKS = ("buggy-pipeline", "plugin-add", "rename-sweep", "orbit-propagator")


def _enrich(rows: list[dict]) -> None:
    for r in rows:
        r["_ok"] = bool((r.get("grade") or {}).get("success"))
        r["_turns"] = r["cli"]["num_turns"]
        r["_out_tokens"] = r["cli"]["usage"]["output_tokens"]
        r["_cost"] = r["cli"]["total_cost_usd"]


def main(root: Path) -> None:
    rows = load_sessions([root / t for t in TASKS],
                         Path(__file__).resolve().parents[1] / "tasks")
    _enrich(rows)

    print("== (1) ability spread among sessions with the SAME outcome ==")
    for t in TASKS:
        ok = [r for r in rows if r["task"] == t and r["_ok"]]
        if len(ok) < 4:
            print(f"  {t}: skipped (success n={len(ok)})")
            continue
        turns = sorted(r["_turns"] for r in ok)
        toks = sorted(r["_out_tokens"] for r in ok)
        cost = sorted(r["_cost"] for r in ok)
        print(f"  {t} (success n={len(ok)}): "
              f"turns {turns[0]}-{turns[-1]} (x{turns[-1]/turns[0]:.1f}), "
              f"out_tokens {toks[0]}-{toks[-1]} (x{toks[-1]/toks[0]:.1f}), "
              f"cost ${cost[0]:.2f}-${cost[-1]:.2f} (x{cost[-1]/cost[0]:.1f})")

    print("\n== (2) is final size visible early? "
          "(Spearman feature@k vs final out_tokens, successes only) ==")
    for t in TASKS:
        trs = [r for r in rows if r["task"] == t and r["_ok"] and r.get("_steps")]
        if len(trs) < 6:
            print(f"  {t}: skipped (success n={len(trs)})")
            continue
        cells = []
        for k in (3, 5, 8):
            for feat in ("cum_exploration", "cum_files_read"):
                xs = [float(r["_steps"][min(k, len(r["_steps"])) - 1][feat])
                      for r in trs]
                ys = [float(r["_out_tokens"]) for r in trs]
                cells.append(f"{feat.removeprefix('cum_')}@{k}="
                             f"{spearman(xs, ys):+.2f}")
        print(f"  {t}: " + " ".join(cells))

    print("\n== (3) token value of early-stopping doomed sessions "
          "(orbit-propagator) ==")
    d = [r for r in rows if r["task"] == "orbit-propagator"]
    total = sum(r["_cost"] for r in d)
    n_ok = sum(r["_ok"] for r in d)
    print(f"  observed: ${total:.2f} for {n_ok} successes "
          f"-> ${total/n_ok:.2f} per success")
    for frac in (0.25, 0.5):
        oracle = sum(r["_cost"] * (1 if r["_ok"] else frac) for r in d)
        print(f"  perfect early-stop of failures at {int(frac*100)}% spend: "
              f"${oracle:.2f} (-{100*(1-oracle/total):.0f}%), "
              f"per-success ${oracle/n_ok:.2f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/main"))
