"""세션이 남긴 것을 뒤 세션이 얼마나 지우고 다시 쓰는가.

**왜 이 값인가** (2026-08-23 유저 설명, `harness/anchor.md` "과정을 측정하는
이유"). 결과를 보지 말라는 것은 결과가 틀려도 된다는 뜻이 아니라, 작은
과제에서는 과정이 나빠도 결과를 되돌리기 쉽고 큰 과제에서는 어렵기
때문이다. 그러면 "과정이 나쁘다"는 **되돌리는 비용이 크다**는 뜻이 되고,
그 비용은 세션이 남긴 것을 뒤 세션이 얼마나 지우고 다시 쓰는가로 산출된다.

**이것은 사후 분석이다. 예측을 봉인하지 않았다.** `docs/CUT_PREDICTIONS.md`
가 봉인한 예측 일곱에 이 값은 없다. 이미 결과를 본 자료에 새 지표를 대는
것이므로, 여기서 나오는 수는 **다음 배치에서 봉인할 예측의 후보**이지 검정
결과가 아니다.

**무엇을 견주는가.** 세션 하나가 한 관측이다. 세션이 시작할 때의 작업 트리와
끝날 때의 작업 트리를 견주어 그 세션이 **더한 줄**을 세고, 사슬이 끝난
시점의 작업 트리에 그 줄이 남아 있는지 본다. 남아 있지 않으면 뒤 세션이
지웠거나 다시 쓴 것이다.

    되돌림 비율 = 사라진 줄 / 그 세션이 더한 줄

**세 가지를 정해 두었다.**

1. **짧은 줄은 세지 않는다.** 공백 줄과 `}` 같은 줄은 어느 파일에나 있어
   남았는지 사라졌는지가 뜻이 없다. 공백을 걷어낸 길이가
   `MIN_SIGNIFICANT` 미만인 줄은 양쪽 셈에서 다 뺀다.
2. **남았는지는 사슬 끝 트리 전체에서 찾는다**, 그 파일 안에서만 찾지
   않는다. 뒤 세션이 파일을 옮기거나 이름을 바꿨을 때 그 줄이 사라졌다고
   세면 안 되기 때문이다. 이 선택은 되돌림을 **적게** 세는 쪽이다.
3. **`.venv/` 같은 경로는 뺀다.** 세션이 만든 가상 환경이 스냅숏에 통째로
   들어가 있다. 안 빼면 사슬 하나에서 더한 줄이 48만으로 나오고 실제 작업이
   묻힌다.

**세션 경계는 시각으로 나눈다.** 스냅숏 커밋에 붙은 번호는 사슬 전체에
이어지는 호출 번호이고 세션 경계를 표시하지 않는다. 대신 트랜스크립트의
첫 시각과 끝 시각으로 세션마다 구간을 만들고, 이웃한 두 세션 사이의
중간 시각을 경계로 삼는다 — 러너가 세션이 끝난 **뒤에** 스냅숏을 한 번 더
찍으므로(`pilot/run_chain.py`), 트랜스크립트 끝 시각을 그대로 경계로 쓰면
그 마지막 스냅숏이 다음 세션 몫으로 넘어간다.

사용:

    python pilot/analysis/rework.py --arm results/cut/keep
    python pilot/analysis/rework.py --arm results/cut/keep --arm results/cut/cut
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cut_eval  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

#: 공백을 걷어낸 길이가 이보다 짧은 줄은 세지 않는다.
MIN_SIGNIFICANT = 3

#: 세션의 작업이 아닌 경로. 세션이 만든 가상 환경과 내려받은 꾸러미다.
EXCLUDED_PREFIXES = (".venv/", ".taskvenv/", "node_modules/", ".git/")

#: **과제가 세션마다 다시 쓰라고 지시하는 문서.** 뒤 세션이 이것을 덮어쓰는
#: 것은 되돌림이 아니라 시킨 대로 한 것이므로 본 셈에서 뺀다.
#: `pilot/tasks/shared-core/prompt.txt` 가 세션마다 `HANDOFF.md` 를 갱신하라고
#: 지시한다. 이 구분을 안 하면 인계 문서를 길게 쓴 세션이 되돌림이 큰 세션으로
#: 잡힌다 — 안 끊는 쪽 c01s06 이 그렇게 잡혔다(더한 줄 126 중 대부분이
#: `HANDOFF.md`, 다음 세션이 그것을 다시 씀).
REWRITTEN_BY_DESIGN = ("HANDOFF.md",)

#: 스냅숏 저장소가 사슬마다 하나씩 들어 있는 디렉토리 이름.
SNAPSHOT_DIR_NAME = "snapshots"


# ------------------------------------------------------------------ git

def _git(git_dir: Path, *args: str) -> str:
    """스냅숏 저장소에 대고 git 을 실행한다.

    부모 git 프로세스의 환경(`GIT_DIR`·`GIT_INDEX_FILE`)을 물려받으면 남의
    저장소를 보게 된다. 이 저장소에서 같은 결함을 세 번 만났다.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(["git", f"--git-dir={git_dir}", *args],
                          capture_output=True, env=env, encoding="utf-8",
                          errors="replace")
    return done.stdout if done.returncode == 0 else ""


def commits(git_dir: Path) -> list[tuple[str, int]]:
    """(해시, 커밋 시각) 을 **오래된 것부터**. `baseline` 도 들어간다."""
    return [(sha, when) for sha, when, _ in numbered_commits(git_dir)]


def numbered_commits(git_dir: Path) -> list[tuple[str, int, int | None]]:
    """(해시, 커밋 시각, 호출 번호). 시작 상태 커밋의 번호는 None.

    호출 번호는 스냅숏 훅이 제목에 적어 둔 것이고 **사슬 전체에 이어진다**
    (`pilot/snapshot.py`). 세션 경계를 표시하지는 않지만, 노출 기간을 호출
    수로 맞추는 데 쓴다.
    """
    out = _git(Path(git_dir), "log", "--reverse", "--format=%H %ct %s")
    rows: list[tuple[str, int, int | None]] = []
    for line in out.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        number = None
        if len(parts) >= 4 and parts[2] == "call" and parts[3].isdigit():
            number = int(parts[3])
        rows.append((parts[0], int(parts[1]), number))
    return rows


# ------------------------------------------------------- 세션 경계 나누기

def session_times(row: dict) -> tuple[float, float] | None:
    """그 세션의 트랜스크립트 첫 시각과 끝 시각(초). 못 읽으면 None."""
    path = row.get("transcript")
    if not path or not Path(path).is_file():
        return None
    stamps = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line).get("timestamp")
            except ValueError:
                continue
            if isinstance(value, str):
                stamps.append(value)
    if not stamps:
        return None
    return _epoch(min(stamps)), _epoch(max(stamps))


def _epoch(stamp: str) -> float:
    from datetime import datetime, timezone
    text = stamp.replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return 0.0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def boundaries(windows: list[tuple[float, float]]) -> list[float]:
    """세션마다 "여기까지가 이 세션" 인 시각.

    이웃한 두 세션 사이의 중간을 쓴다. 마지막 세션은 위가 없으므로 무한대다.
    """
    out: list[float] = []
    for index, (_, end) in enumerate(windows):
        if index + 1 < len(windows):
            out.append((end + windows[index + 1][0]) / 2)
        else:
            out.append(float("inf"))
    return out


def session_trees(rows: list[tuple[str, int]],
                  bounds: list[float]) -> list[tuple[str, str] | None]:
    """세션마다 (시작 트리, 끝 트리) 해시. 그 세션이 아무것도 안 바꿨으면 None.

    `rows` 는 오래된 것부터의 (해시, 시각) 이고 첫 항목이 시작 상태다.
    """
    if not rows:
        return [None] * len(bounds)
    out: list[tuple[str, str] | None] = []
    previous = rows[0][0]
    position = 0
    for bound in bounds:
        start = previous
        end = start
        while position < len(rows) and rows[position][1] <= bound:
            end = rows[position][0]
            position += 1
        out.append(None if end == start else (start, end))
        previous = end
    return out


# ------------------------------------------------------------ 줄 세기

def significant(line: str) -> bool:
    return len(line.strip()) >= MIN_SIGNIFICANT


def excluded(path: str) -> bool:
    """뺄 경로인가.

    `lstrip("./")` 을 쓰지 않는다 — 그것은 접두사가 아니라 **문자 하나하나**를
    벗겨내므로 `.venv/lib` 이 `venv/lib` 이 되어 `.venv/` 와 안 맞는다.
    """
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    return any(path.startswith(prefix) or f"/{prefix}" in path
               for prefix in EXCLUDED_PREFIXES)


def added_lines(git_dir: Path, before: str, after: str,
                only: tuple[str, ...] | None = None) -> Counter[str]:
    """`before` 에서 `after` 로 가면서 **더해진** 줄.

    `only` 를 주면 그 경로만 센다. 안 주면 뺄 경로와 과제가 다시 쓰라고
    지시한 문서를 뺀 나머지를 센다.
    """
    if only is not None:
        paths = list(only)
    else:
        paths = [".", *[f":(exclude){prefix.rstrip('/')}" for prefix in
                        EXCLUDED_PREFIXES],
                 *[f":(exclude){path}" for path in REWRITTEN_BY_DESIGN]]
    out = _git(Path(git_dir), "diff", "-U0", "--no-renames", "--no-color",
               before, after, "--", *paths)
    counted: Counter[str] = Counter()
    for line in out.splitlines():
        if line.startswith("+++") or not line.startswith("+"):
            continue
        text = line[1:]
        if significant(text):
            counted[text.strip()] += 1
    return counted


def tree_lines(git_dir: Path, rev: str) -> Counter[str]:
    """그 시점 작업 트리에 있는 모든 줄. 뺄 경로와 짧은 줄은 빼고 센다."""
    git_dir = Path(git_dir)
    listing = _git(git_dir, "ls-tree", "-r", rev)
    blobs = []
    for line in listing.splitlines():
        head, _, path = line.partition("\t")
        parts = head.split()
        if len(parts) >= 3 and parts[1] == "blob" and not excluded(path):
            blobs.append(parts[2])
    if not blobs:
        return Counter()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(["git", f"--git-dir={git_dir}", "cat-file", "--batch"],
                          input="\n".join(blobs).encode(),
                          capture_output=True, env=env)
    return _parse_batch(done.stdout)


def _parse_batch(data: bytes) -> Counter[str]:
    """`git cat-file --batch` 출력에서 줄을 센다. 이진 파일은 건너뛴다."""
    counted: Counter[str] = Counter()
    position = 0
    while position < len(data):
        newline = data.find(b"\n", position)
        if newline < 0:
            break
        header = data[position:newline].split()
        position = newline + 1
        if len(header) != 3 or not header[2].isdigit():
            break
        size = int(header[2])
        body = data[position:position + size]
        position += size + 1              # 본문 뒤의 줄바꿈 하나
        if b"\x00" in body:
            continue                      # 이진 파일
        for line in body.decode("utf-8", "replace").splitlines():
            if significant(line):
                counted[line.strip()] += 1
    return counted


def gone(added: Counter[str], final: Counter[str]) -> int:
    """더한 줄 가운데 뒤 시점 트리에 남아 있지 않은 줄 수."""
    return sum(max(0, count - final.get(text, 0))
               for text, count in added.items())


# ------------------------------------------------------- 노출 기간 맞추기

#: 되돌림을 볼 기간. 그 세션이 끝난 뒤 몇 호출까지 보는가. 세션 하나의
#: 예산(100)과 같게 두었다.
DEFAULT_HORIZON = 100


def horizon_commit(rows: list[tuple[str, int, int | None]], end_sha: str,
                   horizon: int) -> str | None:
    """`end_sha` 로부터 `horizon` 호출 뒤의 트리. 그만큼 안 남았으면 None.

    **왜 필요한가.** 사슬 끝까지를 견주면 뒤에 앉은 세션일수록 되돌릴 사람이
    적어 비율이 낮게 나온다. 사슬의 **마지막 세션은 구조적으로 언제나 0**이다.
    그러면 위치가 신호로 새어 들어가 세션끼리 견줄 수 없다. 그래서 세션마다
    같은 길이의 기간만 본다.
    """
    numbers = [number for _, _, number in rows if number is not None]
    if not numbers:
        return None
    position = next((index for index, row in enumerate(rows)
                     if row[0] == end_sha), None)
    if position is None:
        return None
    # 그 세션이 끝난 시점의 호출 번호. 시작 상태 커밋이면 0으로 본다.
    at = rows[position][2] or 0
    target = at + horizon
    if max(numbers) < target:
        return None                       # 남은 기간이 모자라다
    chosen = end_sha
    for sha, _, number in rows[position + 1:]:
        if number is not None and number > target:
            break
        chosen = sha
    return chosen


# ------------------------------------------------------------- 한 사슬

def chain_rework(out_dir: Path, chain: int, git_dir: Path,
                 at: int = cut_eval.DEFAULT_AT, start: int | None = None,
                 horizon: int = DEFAULT_HORIZON) -> list[dict]:
    """사슬 하나의 세션마다 되돌림을 산출한다.

    두 가지를 같이 낸다. `rework_ratio` 는 **사슬 끝까지** 본 것이고 위치
    편향이 있다. `rework_ratio_h` 는 세션마다 **같은 길이의 기간**만 본 것이라
    세션끼리 견줄 수 있고, 기간이 모자란 세션은 None 이다.
    """
    rows = cut_eval.load_chain(Path(out_dir), chain)
    windows = [session_times(row) for row in rows]
    if not rows or any(window is None for window in windows):
        return []
    numbered = numbered_commits(git_dir)
    trees = session_trees([(sha, when) for sha, when, _ in numbered],
                          boundaries(windows))  # type: ignore[arg-type]
    head = _git(Path(git_dir), "rev-parse", "HEAD").strip()
    cache: dict[str, Counter[str]] = {}

    def lines_at(rev: str) -> Counter[str]:
        if rev not in cache:
            cache[rev] = tree_lines(git_dir, rev)
        return cache[rev]

    out = []
    before = start
    for index, row in enumerate(rows):
        after = cut_eval.passed(row)
        pair = trees[index] if index < len(trees) else None
        total = missing = handoff_added = handoff_gone = 0
        ratio_h = missing_h = None
        if pair:
            counted = added_lines(git_dir, pair[0], pair[1])
            total = sum(counted.values())
            missing = gone(counted, lines_at(head))
            handoff = added_lines(git_dir, pair[0], pair[1],
                                  only=REWRITTEN_BY_DESIGN)
            handoff_added = sum(handoff.values())
            later = horizon_commit(numbered, pair[1], horizon)
            if later:
                handoff_gone = gone(handoff, lines_at(later))
                if total:
                    missing_h = gone(counted, lines_at(later))
                    ratio_h = missing_h / total
        out.append({
            "chain": row.get("chain", chain),
            "session_index": row.get("session_index", index + 1),
            "label": row.get("label"),
            "cut": bool(row.get("cut")),
            "flagged": cut_eval.flagged(row, at),
            "calls": cut_eval.calls_of(row),
            "gain": None if before is None or after is None else after - before,
            "added_lines": total,
            "gone_lines": missing,
            "rework_ratio": (missing / total) if total else None,
            "gone_lines_h": missing_h,
            "rework_ratio_h": ratio_h,
            # 과제가 다시 쓰라고 지시한 문서. 본 셈과 섞지 않는다.
            "handoff_added_lines": handoff_added,
            "handoff_gone_lines_h": handoff_gone,
        })
        if after is not None:
            before = after
    return out


def arm_rework(out_dir: Path, at: int = cut_eval.DEFAULT_AT,
               start: int | None = None,
               horizon: int = DEFAULT_HORIZON) -> list[dict]:
    out_dir = Path(out_dir)
    snapshots = out_dir / SNAPSHOT_DIR_NAME
    chains = sorted({int(p.name[9:11]) for p in
                     out_dir.glob("session-c*s*.json")})
    rows = []
    for chain in chains:
        git_dir = snapshots / f"chain-{chain:02d}.git"
        if not git_dir.is_dir():
            continue
        rows.extend(chain_rework(out_dir, chain, git_dir, at, start, horizon))
    return rows


# ------------------------------------------------------------ 모아 적기

def _describe(values: list[float]) -> dict:
    values = sorted(values)
    return {
        "n": len(values),
        "median": statistics.median(values) if values else None,
        "mean": (sum(values) / len(values)) if values else None,
        "max": values[-1] if values else None,
    }


def summarize(rows: list[dict], key: str = "rework_ratio_h") -> dict:
    """되돌림 비율의 분포와, 초반 신호로 나눈 두 무리.

    **끊긴 세션은 뺀다.** 열 호출에서 멈춘 세션은 더한 줄이 거의 없어
    비율이 뜻을 갖지 않는다.

    기본값은 노출 기간을 맞춘 `rework_ratio_h` 다. 사슬 끝까지 본
    `rework_ratio` 로 견주려면 `key` 를 바꾼다 — 그 값에는 위치 편향이 있다.

    **아무것도 안 바꾼 세션을 따로 센다.** 되돌릴 것이 없다는 것은 되돌림이
    0이라는 뜻이 아니라 그 세션이 아무것도 안 남겼다는 뜻이므로, 비율에
    0으로 넣으면 안 된다.
    """
    alive = [row for row in rows if not row["cut"]]
    live = [row for row in alive if row.get(key) is not None]
    split: dict[str, dict] = {}
    for name, want in (("flagged", True), ("unflagged", False)):
        picked = [row[key] for row in live if row["flagged"] is want]
        split[name] = _describe(picked)
    idle = [row for row in alive if not row["added_lines"]]
    idle_split = {}
    for name, want in (("flagged", True), ("unflagged", False)):
        group = [row for row in alive if row["flagged"] is want]
        count = sum(1 for row in group if not row["added_lines"])
        idle_split[name] = {"n": len(group), "idle": count,
                            "rate": (count / len(group)) if group else None}
    return {
        "measure": key,
        "n_sessions": len(rows),
        "n_scored": len(live),
        "n_changed_nothing": len(idle),
        "changed_nothing_by_signal": idle_split,
        "all": _describe([row[key] for row in live]),
        "by_signal": split,
        "added_lines_total": sum(row["added_lines"] for row in rows),
        "gone_lines_total": sum(row["gone_lines"] for row in rows),
        "handoff_added_total": sum(row.get("handoff_added_lines", 0)
                                   for row in rows),
        "handoff_gone_total": sum(row.get("handoff_gone_lines_h", 0)
                                  for row in rows),
    }


#: 이만큼 넘게 쓰고도 코드를 하나도 안 남겼으면 헛쓴 세션으로 본다. 그
#: 아래는 끊어도 아낄 것이 없다 — 세션이 스스로 그 전에 끝난다.
WASTE_FLOOR = 20


def wasted_sessions(rows: list[dict], min_calls: int = WASTE_FLOOR) -> dict:
    """호출을 쓰고도 코드를 하나도 안 남긴 세션.

    **끊는 장치가 아낄 수 있는 것이 이것뿐이다.** 코드를 남긴 세션을 끊으면
    남긴 것을 버리는 것이고, 몇 호출 만에 스스로 끝난 세션은 끊어도 아낄
    것이 없다.

    `by_signal` 은 초반 신호가 그 세션들을 잡는지 본다.
    """
    alive = [row for row in rows if not row["cut"]]
    wasted = [row for row in alive
              if row["calls"] >= min_calls and not row["added_lines"]]
    by_signal = {}
    for name, want in (("flagged", True), ("unflagged", False),
                       ("unjudged", None)):
        group = [row for row in alive if row["flagged"] is want]
        caught = [row for row in group if row in wasted]
        by_signal[name] = {"n": len(group), "wasted": len(caught)}
    return {
        "min_calls": min_calls,
        "n": len(wasted),
        "calls": sum(row["calls"] for row in wasted),
        "calls_total": sum(row["calls"] for row in alive),
        "labels": [row["label"] for row in wasted],
        "by_signal": by_signal,
    }


def report(arms: dict[str, Path], at: int = cut_eval.DEFAULT_AT,
           start: int | None = None,
           horizon: int = DEFAULT_HORIZON) -> dict:
    out = {}
    for name, path in arms.items():
        rows = arm_rework(path, at, start, horizon)
        out[name] = {"rows": rows,
                     "summary": summarize(rows, "rework_ratio_h"),
                     "to_chain_end": summarize(rows, "rework_ratio"),
                     "wasted": wasted_sessions(rows)}
    return out


def _render(name: str, block: dict) -> str:
    summary = block["summary"]
    idle = summary["changed_nothing_by_signal"]
    lines = [f"## {name}",
             f"세션 {summary['n_sessions']}개. 더한 줄 "
             f"{summary['added_lines_total']}, 사슬 끝에 없는 줄 "
             f"{summary['gone_lines_total']}.",
             f"인계 문서는 따로 센다(과제가 세션마다 다시 쓰라고 지시한다) — "
             f"더한 줄 {summary['handoff_added_total']}, 뒤 세션이 덮어쓴 줄 "
             f"{summary['handoff_gone_total']}.",
             "",
             f"**파일을 하나도 안 바꾸고 끝난 세션 "
             f"{summary['n_changed_nothing']}개.** 되돌릴 것이 없다는 뜻이지 "
             f"되돌림이 0이라는 뜻이 아니므로 아래 비율에서 뺀다."]
    for key, label in (("flagged", "깃발이 선 세션"),
                       ("unflagged", "깃발이 안 선 세션")):
        part = idle[key]
        if part["rate"] is not None:
            lines.append(f"  {label} {part['n']}개 중 {part['idle']}개 "
                         f"({part['rate']:.0%})")
    lines += ["", f"**되돌림 비율** (세션이 끝난 뒤 같은 길이의 기간만 본다). "
              f"산출된 세션 {summary['n_scored']}개."]
    whole = summary["all"]
    if whole["median"] is None:
        lines.append("  산출된 세션 없음")
    else:
        lines.append(f"  전체 — 중앙값 {whole['median']:.3f}, 평균 "
                     f"{whole['mean']:.3f}, 최대 {whole['max']:.3f}")
    for key, label in (("flagged", "깃발이 선 세션"),
                       ("unflagged", "깃발이 안 선 세션")):
        part = summary["by_signal"][key]
        if part["median"] is None:
            lines.append(f"  {label}: 산출된 세션 없음")
        else:
            lines.append(f"  {label} {part['n']}개 — 중앙값 "
                         f"{part['median']:.3f}, 평균 {part['mean']:.3f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", default=[],
                        help="갈래 결과 디렉토리. 여러 번 줄 수 있다.")
    parser.add_argument("--at", type=int, default=cut_eval.DEFAULT_AT)
    parser.add_argument("--start", type=int, default=None,
                        help="시작 상태의 통과 항목 수.")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON,
                        help="세션이 끝난 뒤 몇 호출까지 되돌림을 보는가.")
    parser.add_argument("--json", default=None, help="원자료를 쓸 파일.")
    args = parser.parse_args(argv)

    if not args.arm:
        parser.error("--arm 을 적어도 하나 줘야 한다")
    arms = {Path(path).name: Path(path) for path in args.arm}
    result = report(arms, args.at, args.start, args.horizon)
    for name, block in result.items():
        print(_render(name, block))
        print()
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"원자료: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
