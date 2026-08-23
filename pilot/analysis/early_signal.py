#!/usr/bin/env python3
"""초반 몇 호출의 행동으로 그 세션이 일을 해낼지 맞힐 수 있는가.

이 프로젝트가 답하려는 질문의 뒤 절반이다(`harness/anchor.md`) — 세션마다
능력이 다르다면, 그 차이를 **초반에** 판별해 끊고 재시작할 수 있는가.

**세 가지를 지킨다.**

1. **문턱을 정한 자료와 판정하는 자료를 가른다.** 사슬 열 개 중 아홉으로
   문턱을 정하고 남은 하나에서 맞히는 것을 열 번 한다. 같은 자료로 둘 다
   하면 맞을 수밖에 없다.
2. **비교 대상을 반드시 같이 낸다.** 아무것도 안 보고 다수 쪽으로 찍는 것과,
   세션 번호만 보는 것. 관측이 필요 없는 값을 못 이기면 그 신호는 쓸모가 없다.
3. **끊어서 이득인지는 여기서 답하지 않는다.** 이 배치는 아무 세션도 끊지
   않았다. 판별 가능성과 끊기의 이득은 다른 질문이다.

사용:

    .venv/bin/python pilot/analysis/early_signal.py results/main3/subsystems-deep
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 파일을 바꾸는 도구들. 이름이 늘어나면 여기에 더한다.
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

#: 도구 호출의 대상이 들어 있을 만한 열쇠. 앞에서부터 처음 찾은 것을 쓴다.
TARGET_KEYS = ("file_path", "path", "notebook_path", "pattern", "command")

#: 시작 상태에서 이미 통과해 있는 달성 항목 수.
START_MARK = 1

#: 달성 항목 전체 수. 여기서 시작하는 세션은 늘릴 것이 없다.
FULL_MARK = 25


def tool_calls(path: Path) -> list[dict]:
    """트랜스크립트의 도구 호출을 순서대로.

    **알 수 없는 줄은 건너뛴다.** 이 JSONL 은 문서화되어 있지 않고 판마다
    다르다(`src/casa/transcript.py` 와 같은 규칙).
    """
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append({"name": block.get("name") or "?",
                            "input": block.get("input") or {}})
    return out


def target_of(call: dict) -> str:
    """그 호출이 무엇을 향했는지. 알 수 없으면 빈 문자열."""
    got = call.get("input") or {}
    for key in TARGET_KEYS:
        value = got.get(key)
        if isinstance(value, str):
            return value
    return ""


def features(head: list[dict]) -> dict:
    """초반 구간에서 뽑는 값들. **전부 세션 밖에서 셀 수 있는 것이다.**"""
    names = [c.get("name") for c in head]
    paths = [target_of(c) for c in head]
    return {
        "reads": sum(1 for n in names if n == "Read"),
        "bash": sum(1 for n in names if n == "Bash"),
        "edits": sum(1 for n in names if n in EDIT_TOOLS),
        "code": sum(1 for p in paths if p.endswith(".py")),
        "docs": sum(1 for p in paths if "/docs/" in p or p.endswith(".md")),
        "distinct": len({p for p in paths if p and "/" in p}),
    }


def sessions(out_dir: Path, window: int) -> list[dict]:
    """세션마다 초반 구간의 값과 그 세션이 항목을 늘렸는지.

    **늘렸는가는 앞 세션과 견주어 정한다.** 사슬 안에서 세션은 앞사람이 남긴
    상태에서 시작하므로, 절대값이 아니라 늘어난 양이 그 세션이 한 일이다.
    """
    out_dir = Path(out_dir)
    per_chain: dict[str, list[dict]] = {}
    for path in sorted(out_dir.glob("session-*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        per_chain.setdefault(str(row.get("label", ""))[:3], []).append(row)

    rows: list[dict] = []
    for chain, group in sorted(per_chain.items()):
        before = START_MARK
        for row in group:
            checks = (row.get("grade") or {}).get("checkpoints") or {}
            after = sum(1 for v in checks.values() if v is True)
            label = str(row.get("label", ""))
            head = tool_calls(out_dir / f"transcript-{label}.jsonl")[:window]
            metrics = ((row.get("audit") or {}).get("metrics") or {})
            rows.append({
                "label": label, "chain": chain,
                "index": row.get("session_index"),
                "before": before, "after": after,
                "advanced": after > before,
                "has_work_left": before < FULL_MARK,
                "calls": metrics.get("n_tool_calls", 0),
                "cost": (row.get("cli") or {}).get("total_cost_usd") or 0.0,
                "minutes": (row.get("wall_s") or 0) / 60,
                **features(head),
            })
            before = after
    return rows


# --------------------------------------------- 사슬 하나씩 빼고 맞히기

def held_out_accuracy(rows: list[dict], fit, guess) -> float:
    """사슬 하나를 빼고 나머지로 정한 뒤, 뺀 사슬에서 맞힌 비율.

    **사슬 단위로 가르는 이유:** 같은 사슬의 세션들은 앞사람이 남긴 상태를
    물려받으므로 서로 독립이 아니다. 세션 단위로 가르면 뺀 세션의 답이 같은
    사슬의 다른 세션에 이미 들어 있다.
    """
    chains = sorted({r["chain"] for r in rows})
    if len(chains) < 2:
        return float("nan")
    hit = total = 0
    for held in chains:
        train = [r for r in rows if r["chain"] != held]
        test = [r for r in rows if r["chain"] == held]
        model = fit(train)
        for row in test:
            hit += int(bool(guess(model, row)) == bool(row["advanced"]))
            total += 1
    return hit / total if total else float("nan")


def majority(rows: list[dict]) -> bool:
    """아무것도 안 보고 다수 쪽으로 찍는다."""
    if not rows:
        return True
    return sum(1 for r in rows if r["advanced"]) * 2 >= len(rows)


def by_index_fit(train: list[dict]) -> dict:
    """세션 번호마다 다수 쪽. **관측이 전혀 필요 없는 값이다.**"""
    out: dict[int, bool] = {}
    for row in train:
        out.setdefault(row["index"], None)
    for index in list(out):
        group = [r["advanced"] for r in train if r["index"] == index]
        out[index] = (sum(group) * 2 >= len(group)) if group else True
    return out


def threshold_fit(key: str):
    """그 값이 문턱 이상이면 '늘린다'로 보는 규칙. 문턱은 훈련 자료에서 고른다.

    같은 점수의 문턱이 여럿이면 **작은 쪽**을 고른다. 그래야 사슬을 바꿔 가며
    돌려도 같은 규칙이 나오고, 결과가 문턱 고르기의 우연에 흔들리지 않는다.
    """
    def fit(train: list[dict]) -> int:
        best, best_hit = 0, -1
        for value in sorted({r[key] for r in train}):
            hit = sum(1 for r in train
                      if (r[key] >= value) == r["advanced"])
            if hit > best_hit:
                best, best_hit = value, hit
        return best
    return fit


def threshold_guess(key: str):
    def guess(model: int, row: dict) -> bool:
        return row[key] >= model
    return guess


def split_rates(rows: list[dict], key: str, threshold: int) -> dict:
    """문턱 위아래에서 항목을 늘린 비율."""
    low = [r for r in rows if r[key] < threshold]
    high = [r for r in rows if r[key] >= threshold]
    return {
        "low_n": len(low), "high_n": len(high),
        "low_adv": sum(1 for r in low if r["advanced"]),
        "high_adv": sum(1 for r in high if r["advanced"]),
        "low_calls": sum(r["calls"] for r in low),
        "low_cost": sum(r["cost"] for r in low),
        "low_minutes": sum(r["minutes"] for r in low),
    }


def shuffle_test(rows: list[dict], key: str, threshold: int,
                 rounds: int = 20000, seed: int = 20260822) -> float:
    """이만큼의 차이가 뒤섞은 자료에서 얼마나 자주 나오는지.

    **작다고 해서 신호가 쓸모 있다는 뜻은 아니다.** 이 값은 관측된 차이가
    자료를 뒤섞어도 흔히 나오는 크기인지만 말한다.
    """
    flags = [r[key] < threshold for r in rows]
    advanced = [r["advanced"] for r in rows]
    low = [a for a, f in zip(advanced, flags) if f]
    high = [a for a, f in zip(advanced, flags) if not f]
    if not low or not high:
        return float("nan")
    observed = sum(high) / len(high) - sum(low) / len(low)
    rng = random.Random(seed)
    at_least = 0
    for _ in range(rounds):
        rng.shuffle(flags)
        a = [v for v, f in zip(advanced, flags) if f]
        b = [v for v, f in zip(advanced, flags) if not f]
        if a and b and (sum(b) / len(b) - sum(a) / len(a)) >= observed:
            at_least += 1
    return at_least / rounds


def report(out_dir: Path, windows=(5, 10, 15)) -> str:
    lines: list[str] = []
    add = lines.append
    add("# 초반 신호 — 초반 몇 호출로 그 세션이 일을 해낼지 맞힐 수 있는가")
    add("")
    add("사슬 열 개 중 아홉으로 문턱을 정하고 남은 하나에서 맞히는 것을 열 번")
    add("한다. **같은 자료로 문턱을 정하고 같은 자료로 판정하지 않는다.**")
    add("")
    for window in windows:
        rows = [r for r in sessions(out_dir, window) if r["has_work_left"]]
        if not rows:
            continue
        base = sum(1 for r in rows if r["advanced"]) / len(rows)
        add(f"## 초반 {window}호출")
        add("")
        add(f"세션 {len(rows)}개 중 항목을 늘린 세션 "
            f"{sum(1 for r in rows if r['advanced'])}개({base:.0%}). "
            "앞 세션이 이미 만점이라 늘릴 것이 없던 세션은 뺐다.")
        add("")
        add("| 무엇으로 맞히나 | 맞힌 비율 |")
        add("|---|---|")
        add(f"| 아무것도 안 보고 다수 쪽 | {max(base, 1 - base):.1%} |")
        add(f"| 세션 번호만 | "
            f"{held_out_accuracy(rows, by_index_fit, lambda m, r: m.get(r['index'], True)):.1%} |")
        for key in ("code", "docs", "reads", "bash", "edits", "distinct"):
            acc = held_out_accuracy(rows, threshold_fit(key),
                                    threshold_guess(key))
            add(f"| 초반 {window}호출의 `{key}` | {acc:.1%} |")
        add("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir")
    ap.add_argument("--window", type=int, default=None,
                    help="이 값만 본다. 안 주면 5·10·15를 다 본다.")
    args = ap.parse_args(argv)
    windows = (args.window,) if args.window else (5, 10, 15)
    sys.stdout.write(report(Path(args.out_dir), windows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
