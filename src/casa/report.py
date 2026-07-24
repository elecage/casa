"""Aggregate analysis over a batch of runner session results.

Input: directories produced by pilot/run_sessions.py (one per task),
each holding session-NN.json summaries and transcript-NN.jsonl files.
Everything here is deterministic and label-free except where task
outcomes (grade.success) are explicitly the labels, per the study
design: labels come from task outcomes, never from the tool.

Statistics are intentionally basic and stdlib-only: Mann-Whitney AUROC
(exact pair counting), univariate Newton logistic with leave-one-out
predictions for Brier/ECE, mean/sd summaries.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from . import metrics as m
from .transcript import parse

DEFAULT_K_GRID = (1, 2, 3, 5, 8, 12, 20)

STEP_FEATURES = ("cum_exploration", "cum_files_read", "cum_coverage",
                 "cum_errors", "cum_error_rate")


# --- loading ------------------------------------------------------------


def load_sessions(result_dirs: list[str | Path],
                  tasks_root: str | Path | None = None) -> list[dict[str, Any]]:
    """One row per session: summary JSON + step series recomputed from the
    saved transcript (the runner stores summary-level audit only)."""
    rows: list[dict[str, Any]] = []
    for result_dir in result_dirs:
        result_dir = Path(result_dir)
        for summary_path in sorted(result_dir.glob("session-*.json")):
            row = json.loads(summary_path.read_text(encoding="utf-8"))
            row["_dir"] = str(result_dir)
            index = row.get("session_index")
            transcript = result_dir / f"transcript-{index:02d}.jsonl"
            row["_steps"] = None
            if transcript.exists():
                relevant = _relevant_files(row.get("task"), tasks_root)
                session = parse(transcript)
                row["_steps"] = m.step_series(session, relevant)
            rows.append(row)
    return rows


def _relevant_files(task: str | None, tasks_root: str | Path | None) -> list[str] | None:
    if not task or not tasks_root:
        return None
    path = Path(tasks_root) / task / "relevant_files.txt"
    if not path.exists():
        return None
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def _success(row: dict) -> bool:
    return bool((row.get("grade") or {}).get("success"))


# --- basic statistics ---------------------------------------------------


def auroc(scores: list[float], labels: list[bool]) -> float | None:
    """Mann-Whitney AUROC by exact pair counting (ties count 1/2).
    None when a class is empty."""
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    wins = sum(1 for p in pos for n in neg if p > n)
    ties = sum(1 for p in pos for n in neg if p == n)
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def pooled_auroc(groups: list[tuple[list[float], list[bool]]]) -> float | None:
    """Within-task pooled AUROC: pair counting restricted to same-task
    pairs, aggregated over tasks (pair-weighted)."""
    wins = ties = pairs = 0
    for scores, labels in groups:
        pos = [s for s, l in zip(scores, labels) if l]
        neg = [s for s, l in zip(scores, labels) if not l]
        pairs += len(pos) * len(neg)
        wins += sum(1 for p in pos for n in neg if p > n)
        ties += sum(1 for p in pos for n in neg if p == n)
    if pairs == 0:
        return None
    return (wins + 0.5 * ties) / pairs


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]] by
    hypergeometric enumeration (sum of tables no more probable than the
    observed one). Deterministic, exact for the small n of this study."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def hyper(x: int) -> float:
        return (math.comb(c1, x) * math.comb(n - c1, r1 - x)) / math.comb(n, r1)
    p_obs = hyper(a)
    lo, hi = max(0, r1 + c1 - n), min(r1, c1)
    return min(1.0, sum(hyper(x) for x in range(lo, hi + 1)
                        if hyper(x) <= p_obs + 1e-12))


def mannwhitney_exact(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(U statistic of xs, two-sided exact p) by full enumeration of group
    assignments; two-sided via |U - mean| deviation, ties count 1/2.
    Intended for the small batches of this study (comb(n, k) blows up)."""
    from itertools import combinations
    pooled = list(xs) + list(ys)
    n, k = len(pooled), len(xs)
    def ustat(idx: tuple[int, ...]) -> float:
        chosen = set(idx)
        grp = [pooled[i] for i in idx]
        oth = [pooled[i] for i in range(n) if i not in chosen]
        return (sum(1 for g in grp for o in oth if g > o)
                + 0.5 * sum(1 for g in grp for o in oth if g == o))
    u_obs = ustat(tuple(range(k)))
    mean_u = k * (n - k) / 2
    dev_obs = abs(u_obs - mean_u)
    total = extreme = 0
    for idx in combinations(range(n), k):
        total += 1
        if abs(ustat(idx) - mean_u) >= dev_obs - 1e-9:
            extreme += 1
    return u_obs, extreme / total


def spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation with average ranks for ties. 0.0 when
    either variable is constant."""
    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                ranks[order[t]] = avg
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx)
                    * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def logistic_loo_probs(xs: list[float], labels: list[bool]) -> list[float] | None:
    """Leave-one-out predicted probabilities from a univariate logistic
    model fit by Newton iterations. Deterministic; None if degenerate."""
    if len(set(labels)) < 2 or len(xs) < 4:
        return None
    mu = statistics.fmean(xs)
    sd = statistics.pstdev(xs) or 1.0
    zs = [(x - mu) / sd for x in xs]

    def fit(z: list[float], y: list[bool]) -> tuple[float, float]:
        b0 = b1 = 0.0
        for _ in range(30):
            g0 = g1 = h00 = h01 = h11 = 0.0
            for zi, yi in zip(z, y):
                p = 1.0 / (1.0 + math.exp(-(b0 + b1 * zi)))
                w = max(p * (1.0 - p), 1e-9)
                g0 += p - yi
                g1 += (p - yi) * zi
                h00 += w
                h01 += w * zi
                h11 += w * zi * zi
            h00 += 1e-6
            h11 += 1e-6
            det = h00 * h11 - h01 * h01
            if abs(det) < 1e-12:
                break
            d0 = (h11 * g0 - h01 * g1) / det
            d1 = (h00 * g1 - h01 * g0) / det
            b0 -= d0
            b1 -= d1
            if abs(d0) + abs(d1) < 1e-10:
                break
        return b0, b1

    probs = []
    for i in range(len(zs)):
        z_train = zs[:i] + zs[i + 1:]
        y_train = labels[:i] + labels[i + 1:]
        if len(set(y_train)) < 2:
            return None
        b0, b1 = fit(z_train, y_train)
        probs.append(1.0 / (1.0 + math.exp(-(b0 + b1 * zs[i]))))
    return probs


def brier(probs: list[float], labels: list[bool]) -> float:
    return statistics.fmean((p - y) ** 2 for p, y in zip(probs, labels))


def ece(probs: list[float], labels: list[bool], bins: int = 10) -> float:
    total = len(probs)
    out = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        members = [(p, y) for p, y in zip(probs, labels)
                   if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if members:
            avg_p = statistics.fmean(p for p, _ in members)
            avg_y = statistics.fmean(float(y) for _, y in members)
            out += len(members) / total * abs(avg_p - avg_y)
    return out


# --- feature extraction -------------------------------------------------


def feature_at_k(row: dict, feature: str, k: int) -> float | None:
    steps = row.get("_steps")
    if not steps:
        return None
    step = steps[min(k, len(steps)) - 1]
    value = step.get(feature)
    return float(value) if value is not None else None


def heuristic_flag(row: dict) -> bool:
    """Simple-heuristic baseline: flag likely failure when the session
    edited before exploring, looped, or committed without testing."""
    met = (row.get("audit") or {}).get("metrics") or {}
    violations = (row.get("audit") or {}).get("violations") or []
    edited_blind = met.get("exploration_before_first_edit") == 0
    looped = (met.get("max_repetition") or 0) >= 3
    untested_commit = any(v.get("rule_id") == "canary-test-before-commit"
                          for v in violations)
    return edited_blind or looped or untested_commit


# --- report assembly ----------------------------------------------------


def _behavior_stats(rows: list[dict]) -> dict[str, Any]:
    def col(path: tuple[str, ...]) -> list[float]:
        out = []
        for row in rows:
            cur: Any = row
            for key in path:
                cur = (cur or {}).get(key) if isinstance(cur, dict) else None
            if isinstance(cur, (int, float)):
                out.append(float(cur))
        return out

    def summarize(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        return {
            "mean": round(statistics.fmean(values), 3),
            "sd": round(statistics.pstdev(values), 3),
            "min": min(values),
            "max": max(values),
        }

    return {
        "exploration_before_first_edit":
            summarize(col(("audit", "metrics", "exploration_before_first_edit"))),
        "coverage": summarize(col(("audit", "metrics", "coverage"))),
        "n_tool_calls": summarize(col(("audit", "metrics", "n_tool_calls"))),
        "wall_s": summarize(col(("wall_s",))),
        "cost_usd": summarize(col(("cli", "total_cost_usd"))),
    }


def _violation_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for violation in (row.get("audit") or {}).get("violations") or []:
            rule = violation.get("rule_id", "?")
            counts[rule] = counts.get(rule, 0) + 1
    return dict(sorted(counts.items()))


def build_report(result_dirs: list[str | Path],
                 tasks_root: str | Path | None = None,
                 k_grid: tuple[int, ...] = DEFAULT_K_GRID) -> dict[str, Any]:
    rows = load_sessions(result_dirs, tasks_root)
    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(row.get("task", "?"), []).append(row)

    tasks = {}
    for task, task_rows in sorted(by_task.items()):
        labels = [_success(r) for r in task_rows]
        tasks[task] = {
            "n": len(task_rows),
            "successes": sum(labels),
            "success_rate": round(sum(labels) / len(task_rows), 3),
            "behavior": _behavior_stats(task_rows),
            "violations": _violation_counts(task_rows),
        }

    # AUROC@k per feature: per task and within-task pooled.
    auroc_at_k: dict[str, dict[str, Any]] = {}
    for feature in STEP_FEATURES:
        feature_out: dict[str, Any] = {"per_task": {}, "pooled": {}}
        for k in k_grid:
            groups = []
            for task, task_rows in sorted(by_task.items()):
                pairs = [(feature_at_k(r, feature, k), _success(r))
                         for r in task_rows]
                pairs = [(s, y) for s, y in pairs if s is not None]
                if pairs:
                    scores, labels = zip(*pairs)
                    groups.append((list(scores), list(labels)))
                    feature_out["per_task"].setdefault(task, {})[str(k)] = \
                        None if (v := auroc(list(scores), list(labels))) is None \
                        else round(v, 3)
            pooled = pooled_auroc(groups)
            feature_out["pooled"][str(k)] = None if pooled is None else round(pooled, 3)
        auroc_at_k[feature] = feature_out

    # Calibration on the headline end-state feature (coverage at last k).
    calibration = {}
    k_last = k_grid[-1]
    pairs = [(feature_at_k(r, "cum_coverage", k_last), _success(r)) for r in rows]
    pairs = [(s, y) for s, y in pairs if s is not None]
    if len(pairs) >= 8:
        xs, labels = map(list, zip(*pairs))
        probs = logistic_loo_probs(xs, labels)
        if probs is not None:
            calibration = {
                "feature": "cum_coverage",
                "k": k_last,
                "n": len(probs),
                "brier": round(brier(probs, labels), 4),
                "ece": round(ece(probs, labels), 4),
            }

    # Baselines.
    labels_all = [_success(r) for r in rows]
    flags = [heuristic_flag(r) for r in rows]
    flagged_failures = sum(1 for f, y in zip(flags, labels_all) if f and not y)
    baselines = {
        "always_continue": {"success_base_rate":
                            round(sum(labels_all) / len(labels_all), 3) if rows else None},
        "simple_heuristic": {
            "auroc": None if (v := auroc([0.0 if f else 1.0 for f in flags],
                                         labels_all)) is None else round(v, 3),
            "flagged": sum(flags),
            "flag_precision_for_failure":
                round(flagged_failures / sum(flags), 3) if sum(flags) else None,
            "failure_recall":
                round(flagged_failures / (len(labels_all) - sum(labels_all)), 3)
                if len(labels_all) - sum(labels_all) else None,
        },
    }

    return {
        "n_sessions": len(rows),
        "tasks": tasks,
        "auroc_at_k": auroc_at_k,
        "calibration": calibration,
        "baselines": baselines,
        "k_grid": list(k_grid),
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    lines = ["# CASA batch report", "",
             f"Sessions: {report['n_sessions']}", "", "## Tasks", ""]
    for task, stats in report["tasks"].items():
        lines.append(f"### {task}")
        lines.append(f"- success: {stats['successes']}/{stats['n']} "
                     f"({stats['success_rate']:.0%})")
        behavior = stats["behavior"]
        for key in ("exploration_before_first_edit", "coverage", "cost_usd"):
            s = behavior.get(key)
            if s:
                lines.append(f"- {key}: mean {s['mean']} sd {s['sd']} "
                             f"[{s['min']}, {s['max']}]")
        if stats["violations"]:
            lines.append(f"- violations: {stats['violations']}")
        lines.append("")
    lines += ["## AUROC@k (within-task pooled)", ""]
    header = "| feature | " + " | ".join(f"k={k}" for k in report["k_grid"]) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(report["k_grid"]) + 1))
    for feature, data in report["auroc_at_k"].items():
        cells = [str(data["pooled"].get(str(k), "-")) for k in report["k_grid"]]
        lines.append(f"| {feature} | " + " | ".join(cells) + " |")
    if report["calibration"]:
        c = report["calibration"]
        lines += ["", f"Calibration ({c['feature']}@k={c['k']}, LOO logistic, "
                      f"n={c['n']}): Brier {c['brier']}, ECE {c['ece']}"]
    b = report["baselines"]
    lines += ["", "## Baselines", "",
              f"- always-continue success base rate: "
              f"{b['always_continue']['success_base_rate']}",
              f"- simple heuristic: AUROC {b['simple_heuristic']['auroc']}, "
              f"flagged {b['simple_heuristic']['flagged']} "
              f"(precision-for-failure {b['simple_heuristic']['flag_precision_for_failure']}, "
              f"failure recall {b['simple_heuristic']['failure_recall']})"]
    return "\n".join(lines) + "\n"
