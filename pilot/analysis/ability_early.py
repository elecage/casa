#!/usr/bin/env python3
"""Early detection on the ABILITY axis (the user's actual question).

Every early-prediction number reported so far targeted the pass/fail bit,
which is near-deterministic per condition, so there was nothing to predict.
The recorded research question (docs/RESEARCH_PLAN.md, revision of
2026-07-24) names two other prediction targets that were never computed:

  target "expensive"  -- this session will finish in the costly tail of its
                         condition (final output tokens, top quartile).
                         Wall-clock is never used (serving-load confound).
  target "false_done" -- this session will claim completion while failing
                         the hidden oracle.

Predictors are restricted to what is visible after the first k tool calls
(k = 2, 4, 8, 16), so a decision could actually be taken at that point.

Reported per condition (task x model, no pooling across conditions --
pooling was what destroyed the signal in the earlier analysis):

  1. spread of the target itself (is there anything to detect?)
  2. discrimination of each early feature at each k (AUROC: 0.5 = coin
     flip, 1.0 = perfect; below 0.5 means the feature points the other way)
  3. the restart rule: tokens per success under "kill at step k and start
     a fresh session" vs. never intervening -- with the cost of killing a
     session that would have succeeded included, not assumed away.

Usage (needs the local, gitignored collections):

    .venv/Scripts/python.exe pilot/analysis/ability_early.py results/main2/* \
        --tasks-root pilot/tasks
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from casa import metrics as m                     # noqa: E402
from casa.report import auroc, _relevant_files    # noqa: E402
from casa.transcript import parse                 # noqa: E402

KS = (2, 4, 8, 16)

FEATURES = (
    "out_tokens",      # output tokens burned so far  (cheap, direct)
    "explore",         # exploration calls so far
    "files_read",
    "coverage",        # fraction of the task's relevant files read
    "errors",
    "repetition",      # largest number of identical calls so far
    "test_runs",
    "aux_checks",      # self-written checks (not the bundled test suite)
    "violations",      # instruction violations so far
    "mutated",         # has it started editing?
)


# --- prefix features ----------------------------------------------------


def token_prefix(transcript: Path) -> list[int]:
    """Cumulative assistant output tokens at each tool call, in call order.

    Walks the raw JSONL because the parser keeps calls, not usage. Entry i
    is the output tokens spent up to and including the message that issued
    call i.

    One assistant message is written out once per content block, each copy
    carrying the same usage record, so tokens are counted once per message
    id -- summing every record inflates the total (measured: 43131 against
    the CLI's own 15906 for orbit session 1). Records without an id are
    counted once each, which is the best available fallback.
    """
    totals: list[int] = []
    running = 0
    counted: set[str] = set()
    text = transcript.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(rec, dict) or rec.get("type") != "assistant":
            continue
        message = rec.get("message") or {}
        usage = message.get("usage") or {}
        out = usage.get("output_tokens")
        message_id = message.get("id")
        fresh = not isinstance(message_id, str) or message_id not in counted
        if isinstance(message_id, str):
            counted.add(message_id)
        if isinstance(out, int) and fresh:
            running += out
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    totals.append(running)
    return totals


def features_at(session, tokens: list[int], violations: list[dict],
                relevant: list[str] | None, k: int) -> dict[str, float] | None:
    """Signals computable from the first k tool calls only."""
    calls = session.tool_calls[:k]
    if len(calls) < k:
        return None                      # session ended before step k

    seen: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    explore = errors = tests = aux = 0
    mutated = False
    for call in calls:
        if call.is_exploration:
            explore += 1
        if call.is_error:
            errors += 1
        if call.is_mutation:
            mutated = True
        if m._is_test_run(call):
            tests += 1
        if m._is_aux_check(call):
            aux += 1
        if call.name == "Read":
            fp = call.input.get("file_path")
            if isinstance(fp, str):
                seen.add(str(Path(fp)))
        key = m._normalized_key(call)
        counts[key] = counts.get(key, 0) + 1

    coverage = None
    if relevant:
        norm = [str(Path(f)) for f in relevant]
        hit = sum(1 for f in norm if f in seen or any(s.endswith(f) for s in seen))
        coverage = hit / len(norm)

    return {
        "out_tokens": float(tokens[k - 1]) if len(tokens) >= k else None,
        "explore": float(explore),
        "files_read": float(len(seen)),
        "coverage": coverage,
        "errors": float(errors),
        "repetition": float(max(counts.values())),
        "test_runs": float(tests),
        "aux_checks": float(aux),
        "violations": float(sum(1 for v in violations
                                if isinstance(v.get("call_index"), int)
                                and v["call_index"] < k)),
        "mutated": 1.0 if mutated else 0.0,
    }


# --- loading ------------------------------------------------------------


def load_condition(result_dir: Path, tasks_root: Path | None) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    meta_path = result_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = []
    for summary_path in sorted(result_dir.glob("session-*.json")):
        row = json.loads(summary_path.read_text(encoding="utf-8"))
        idx = row.get("session_index")
        transcript = result_dir / f"transcript-{idx:02d}.jsonl"
        if not transcript.exists():
            continue
        session = parse(transcript)
        relevant = _relevant_files(row.get("task"), tasks_root)
        violations = (row.get("audit") or {}).get("violations") or []
        tokens = token_prefix(transcript)
        cli = row.get("cli") or {}
        usage = cli.get("usage") or {}
        final_tokens = usage.get("output_tokens")
        if not isinstance(final_tokens, int) or final_tokens <= 0:
            # Session killed (timeout) or no CLI result: fall back to the
            # transcript. Degenerate runs are exactly what the detector is
            # for, so they must not be silently dropped.
            final_tokens = tokens[-1] if tokens else None
        rows.append({
            "index": idx,
            "success": bool((row.get("grade") or {}).get("success")),
            "claims": bool(((row.get("audit") or {}).get("metrics") or {})
                           .get("claims_completion")),
            "final_tokens": final_tokens,
            "n_calls": session.n_tool_calls,
            "prefix": {k: features_at(session, tokens, violations, relevant, k)
                       for k in KS},
        })
    return {"dir": str(result_dir), "task": meta.get("task", result_dir.name),
            "model": meta.get("model", "?"), "rows": rows}


# --- targets ------------------------------------------------------------


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def label_expensive(rows: list[dict], q: float = 0.75) -> list[bool | None]:
    """Top-quartile final output tokens within the condition."""
    known = [r["final_tokens"] for r in rows
             if isinstance(r["final_tokens"], (int, float))]
    if len(known) < 4:
        return [None] * len(rows)
    cut = quantile([float(v) for v in known], q)
    return [None if not isinstance(r["final_tokens"], (int, float))
            else float(r["final_tokens"]) >= cut for r in rows]


def label_false_done(rows: list[dict]) -> list[bool | None]:
    """Claimed completion but failed the hidden oracle."""
    return [bool(r["claims"] and not r["success"]) for r in rows]


# --- restart rule -------------------------------------------------------


def restart_policy(rows: list[dict], labels: list[bool | None], k: int,
                   feature: str) -> dict[str, Any] | None:
    """Tokens per success when a session flagged at step k is killed and
    replaced by a fresh one.

    The replacement is priced at the condition's own unconditional mean
    tokens and success rate, so killing a session that would have
    succeeded is paid for -- both the lost success and the restart.
    Thresholds are the observed feature values; the best one is reported
    together with the do-nothing baseline it has to beat.
    """
    # Every session with a known cost takes part. A session that ended
    # before step k simply cannot be flagged -- dropping those would price
    # the policy on long sessions only and flatter it.
    usable = [r for r in rows if isinstance(r["final_tokens"], (int, float))]
    scorable = [r for r in usable
                if r["prefix"].get(k)
                and r["prefix"][k].get(feature) is not None
                and r["prefix"][k].get("out_tokens") is not None]
    if len(usable) < 8 or len(scorable) < 4:
        return None
    tokens = [float(r["final_tokens"]) for r in usable]
    n_success = sum(1 for r in usable if r["success"])
    if n_success == 0:
        return None
    mean_tokens = statistics.fmean(tokens)
    p_success = n_success / len(usable)
    baseline = sum(tokens) / n_success

    best = None
    for threshold in sorted({r["prefix"][k][feature] for r in scorable}):
        spent = 0.0
        gained = 0.0
        killed = successes_killed = 0
        for r in usable:
            pre = r["prefix"].get(k)
            score = pre.get(feature) if pre else None
            if score is not None and score >= threshold:  # kill and restart
                spent += float(pre["out_tokens"]) + mean_tokens
                gained += p_success
                killed += 1
                if r["success"]:
                    successes_killed += 1
            else:
                spent += float(r["final_tokens"])
                gained += 1.0 if r["success"] else 0.0
        if gained <= 0:
            continue
        per_success = spent / gained
        if best is None or per_success < best["tokens_per_success"]:
            best = {"threshold": threshold, "tokens_per_success": per_success,
                    "killed": killed, "successes_killed": successes_killed}
    if best is None:
        return None
    best.update({"baseline_tokens_per_success": baseline,
                 "saving_pct": 100.0 * (baseline - best["tokens_per_success"]) / baseline,
                 "n": len(usable), "n_scorable": len(scorable),
                 "k": k, "feature": feature})
    return best


# --- report -------------------------------------------------------------


def waste_accounting(rows: list[dict], k: int = 8) -> dict[str, Any] | None:
    """The ceiling on any early-stopping policy, before any prediction.

    Splits the condition's total output tokens into what failing sessions
    burned after step k (the most a perfect detector could ever recover)
    and what successful sessions burned after step k (what a detector that
    stops everything would destroy). If the recoverable share is small, no
    detector can help however accurate it is.
    """
    usable = [r for r in rows if isinstance(r["final_tokens"], (int, float))]
    if not usable:
        return None
    total = sum(float(r["final_tokens"]) for r in usable)
    after_fail = after_ok = 0.0
    for r in usable:
        pre = r["prefix"].get(k)
        spent_by_k = float(pre["out_tokens"]) if pre and pre.get("out_tokens") is not None \
            else float(r["final_tokens"])
        remainder = max(0.0, float(r["final_tokens"]) - spent_by_k)
        if r["success"]:
            after_ok += remainder
        else:
            after_fail += remainder
    return {"k": k, "total": total, "recoverable": after_fail,
            "at_risk": after_ok,
            "recoverable_pct": 100.0 * after_fail / total if total else 0.0,
            "at_risk_pct": 100.0 * after_ok / total if total else 0.0}


def kill_all_policy(rows: list[dict], k: int) -> dict[str, Any] | None:
    """The null policy: kill EVERY session at step k and restart, using no
    signal whatsoever.

    Indispensable as a comparison. In a condition where almost nothing
    succeeds, "stop early and re-roll" improves tokens-per-success on its
    own arithmetic, so a detector that merely matches this number has
    demonstrated no ability to tell sessions apart.
    """
    usable = [r for r in rows if isinstance(r["final_tokens"], (int, float))]
    if len(usable) < 8:
        return None
    n_success = sum(1 for r in usable if r["success"])
    if n_success == 0:
        return None
    mean_tokens = statistics.fmean([float(r["final_tokens"]) for r in usable])
    p_success = n_success / len(usable)
    spent = gained = 0.0
    killed = successes_killed = 0
    for r in usable:
        pre = r["prefix"].get(k)
        if pre and pre.get("out_tokens") is not None:
            spent += float(pre["out_tokens"]) + mean_tokens
            gained += p_success
            killed += 1
            if r["success"]:
                successes_killed += 1
        else:
            spent += float(r["final_tokens"])
            gained += 1.0 if r["success"] else 0.0
    if gained <= 0:
        return None
    return {"k": k, "tokens_per_success": spent / gained, "killed": killed,
            "successes_killed": successes_killed}


def discrimination(rows: list[dict],
                   labels: list[bool | None]) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for feature in FEATURES:
        per_k: dict[int, float] = {}
        for k in KS:
            scores, labs = [], []
            for r, lab in zip(rows, labels):
                if lab is None:
                    continue
                pre = r["prefix"].get(k)
                if not pre or pre.get(feature) is None:
                    continue
                scores.append(float(pre[feature]))
                labs.append(bool(lab))
            if len(set(labs)) == 2 and len(labs) >= 8:
                value = auroc(scores, labs)
                if value is not None:
                    per_k[k] = value
        if per_k:
            out[feature] = per_k
    return out


def sample_at(rows: list[dict], labels: list[bool | None],
              k: int) -> tuple[int, int]:
    """How many labelled sessions even reach step k, and how many of those
    are positive -- printed so a k-column computed on a shrinking, biased
    subsample cannot be read as if it used the whole condition.
    """
    kept = [lab for r, lab in zip(rows, labels)
            if lab is not None and r["prefix"].get(k)]
    return sum(1 for lab in kept if lab), len(kept)


def describe(condition: dict[str, Any]) -> None:
    rows = condition["rows"]
    print(f"\n=== {condition['task']} / {condition['model']} "
          f"(n={len(rows)}, {condition['dir']}) ===")
    tokens = [r["final_tokens"] for r in rows
              if isinstance(r["final_tokens"], (int, float))]
    if tokens:
        print(f"final output tokens: min {min(tokens):.0f} / median "
              f"{statistics.median(tokens):.0f} / max {max(tokens):.0f} "
              f"(x{max(tokens) / max(min(tokens), 1):.1f} spread); "
              f"reached step 16: {sum(1 for r in rows if r['prefix'].get(16))}"
              f"/{len(rows)}")
    print(f"successes {sum(1 for r in rows if r['success'])}, "
          f"false completions "
          f"{sum(1 for r in rows if r['claims'] and not r['success'])}")
    waste = waste_accounting(rows, k=8)
    if waste:
        print(f"spend after step 8: {waste['recoverable_pct']:.0f}% of all "
              f"tokens is burned by sessions that go on to fail (the most a "
              f"perfect detector could recover), {waste['at_risk_pct']:.0f}% "
              f"by sessions that go on to succeed (what stopping them "
              f"destroys)")

    targets = [("expensive", label_expensive(rows)),
               ("false_done", label_false_done(rows))]
    successes = [r for r in rows if r["success"]]
    if len(successes) >= 8:
        # "succeeds but costs far more than its peers" -- the user's own
        # phrasing of the ability axis, with the outcome held fixed.
        succ_labels = label_expensive(successes)
        by_index = {r["index"]: lab for r, lab in zip(successes, succ_labels)}
        targets.append(("expensive_among_successes",
                        [by_index.get(r["index"]) if r["success"] else None
                         for r in rows]))

    for name, labels in targets:
        present = [lab for lab in labels if lab is not None]
        if len(set(present)) < 2:
            print(f"\n-- target {name}: no variance in this condition, skipped")
            continue
        print(f"\n-- target {name} "
              f"({sum(1 for x in present if x)}/{len(present)} positive)")
        counts = {k: sample_at(rows, labels, k) for k in KS}
        print("   sessions reaching step   "
              + "".join(f"  {counts[k][1]:<3d}({counts[k][0]}+) " for k in KS))
        table = discrimination(rows, labels)
        print("   feature        " + "".join(f"  k={k:<5}" for k in KS))
        for feature, per_k in table.items():
            cells = "".join(f"  {per_k[k]:<7.2f}" if k in per_k else "  --     "
                            for k in KS)
            print(f"   {feature:<15}{cells}")
        if name.startswith("expensive"):
            def scan(pool: tuple[str, ...]) -> dict[str, Any] | None:
                best = None
                for k in KS:
                    for feature in pool:
                        got = restart_policy(rows, labels, k, feature)
                        if got and (best is None or got["tokens_per_success"]
                                    < best["tokens_per_success"]):
                            best = got
                return best

            # The token cutoff is the trivial baseline the plan names; a
            # behavioural signal only matters if it beats that.
            null = [got for got in (kill_all_policy(rows, k) for k in KS) if got]
            if null:
                worst = min(null, key=lambda g: g["tokens_per_success"])
                print(f"   null policy (kill EVERY session, no signal): "
                      f"{worst['tokens_per_success']:.0f} tokens/success at "
                      f"step {worst['k']} -- a detector must beat this, not "
                      f"just the do-nothing number")
            for tag, pool in (("token cutoff", ("out_tokens",)),
                              ("behaviour", tuple(f for f in FEATURES
                                                  if f != "out_tokens"))):
                got = scan(pool)
                if not got:
                    print(f"   restart rule ({tag}): not computable")
                    continue
                print(f"   restart rule ({tag}): flag {got['feature']} >= "
                      f"{got['threshold']:.0f} at step {got['k']} -> "
                      f"{got['tokens_per_success']:.0f} tokens/success vs "
                      f"{got['baseline_tokens_per_success']:.0f} doing nothing "
                      f"({got['saving_pct']:+.1f}%); killed {got['killed']}, "
                      f"of which {got['successes_killed']} would have succeeded")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--tasks-root", default=None)
    args = ap.parse_args(argv)
    tasks_root = Path(args.tasks_root) if args.tasks_root else None
    for d in args.dirs:
        path = Path(d)
        if not path.is_dir():
            continue
        condition = load_condition(path, tasks_root)
        if condition["rows"]:
            describe(condition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
