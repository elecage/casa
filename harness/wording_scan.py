#!/usr/bin/env python3
"""트랜스크립트에 글쓰기 규칙 검사를 실행해 무엇이 몇 번 걸렸는지 낸다.

**왜 있나.** `wording_check.py` 는 세션 끝에 한 번 판정하고 만다. 목록을 고칠
때는 그 목록이 실제 글에서 무엇을 검출하고 무엇을 잘못 검출하는지 봐야 한다.
2026-08-24에 목록 첫 판을 이 도구로 확인했고, `돌려준다`(값을 반환한다)와
`프록시가 막혔다` 를 위반으로 잘못 판정하는 것을 찾아 좁혔다.

**이 도구는 분석이 아니라 하네스의 일부다.** `pilot/analysis/` 가 아니라
여기 있는 이유는, 수집 자료가 아니라 우리 세션의 글을 보기 때문이다.

    python harness/wording_scan.py <트랜스크립트.jsonl> [--samples 5]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wording_check as wc  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def assistant_messages(transcript: Path) -> list[str]:
    """기록에서 세션이 유저에게 보낸 글만 뽑는다. 도구 호출은 뺀다."""
    out: list[str] = []
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        text = "".join(item.get("text", "") for item in content
                       if isinstance(item, dict) and item.get("type") == "text")
        if text.strip():
            out.append(text)
    return out


def scan(messages: list[str]) -> dict:
    """답마다 판정하고 항목별로 센다. 표본을 같이 담아 눈으로 확인할 수 있게 한다."""
    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    flagged = 0
    for text in messages:
        hits = wc.find_violations(text)
        ratios = wc.find_bare_ratios(text)
        if hits or ratios:
            flagged += 1
        for hit in hits:
            counts[hit["name"]] += 1
            samples.setdefault(hit["name"], []).append(
                _context(wc.strip_code(text), hit["found"]))
        for ratio in ratios:
            counts["분모 없는 비율"] += 1
            samples.setdefault("분모 없는 비율", []).append(
                _context(wc.strip_tables(wc.strip_code(text)), ratio))
    return {"messages": len(messages), "flagged": flagged,
            "counts": dict(counts), "samples": samples}


def _context(prose: str, token: str, width: int = 34) -> str:
    index = prose.find(token)
    if index < 0:
        return token
    piece = prose[max(index - width, 0): index + len(token) + width]
    return re.sub(r"\s+", " ", piece).strip()


def render(result: dict, samples: int = 0) -> str:
    lines = [f"어긴 것으로 판정된 답 {result['flagged']}개 "
             f"/ 검사한 답 {result['messages']}개"]
    for name, count in sorted(result["counts"].items(),
                              key=lambda kv: -kv[1]):
        lines.append(f"  {count:>4}  {name}")
        for text in random.sample(result["samples"].get(name, []),
                                  min(samples, len(result["samples"].get(name, [])))):
            lines.append(f"          {text}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--samples", type=int, default=0,
                        help="항목마다 보여 줄 표본 수 (눈으로 확인할 때)")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    random.seed(args.seed)
    messages = assistant_messages(args.transcript)
    if not messages:
        print("답을 하나도 못 읽었다. 경로를 확인할 것.")
        return 1
    print(render(scan(messages), args.samples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
