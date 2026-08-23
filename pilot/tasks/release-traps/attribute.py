#!/usr/bin/env python3
"""릴리스 항목별 호출 귀속 — **바꾼 파일**로 정한다 (2026-08-20 유저 결정).

**왜 필요한가.** 쏠림 창과 비율은 "릴리스 항목 하나에 쓴 호출 수"가 있어야
도출된다(`docs/PROBE_PROTOCOL.md` 5절). 프로브 때는 그 귀속 방법이 규약에
없어서 **도출 불가**로 남았고 하한(10 / 0.5)을 썼다.

**왜 바꾼 파일인가.** 스냅숏 저장소의 커밋 사이 차이는 참값이다. 호출 이름과
인자를 보고 무엇을 했는지 추정하면 프로브에서 빗나간 예측 4와 **같은 종류의
오차**가 난다 — `git add` 는 색인만 바꾸므로 과다로, 세션이 돌린 프로그램이
쓰는 출력은 도구 이름에 안 나오므로 과소로 어긋난다.

규칙 셋:

1. 한 호출이 바꾼 파일이 **전부 한 항목**에 들면 그 항목에 귀속한다.
2. **두 항목 이상**에 걸치면 미귀속이다. 어느 쪽에 얼마나인지 지어낼 근거가
   없다.
3. **어느 항목에도 안 들면** 미귀속이다(버전 문자열·변경 기록 같은 절차
   파일, 부산물).

비율은 **귀속된 호출만으로** 잰다. 미귀속 호출을 분모에 넣으면 항목 경계
밖에서 헤맨 세션이 오히려 쏠림이 낮게 나온다.

경로가 겹치면 **더 긴 접두사가 이긴다.** 합계 어긋남의 원인 파일은
`usagectl/readers/` 아래에 있지만 1번 항목이 아니라 5번 항목의 일이다.

영역 경계를 여기 고정하는 것은 `docs/RECOVERY_RULE.md` 9절 4번이 요구한 것이다
— 영역을 잘게 쪼개면 쏠림이 과소평가된다.
"""

from __future__ import annotations

import statistics

#: 릴리스 항목 일곱 개(`template/RELEASE.md`). 짧은 키와 그 뜻.
ITEMS = {
    "sources": "1. 원천을 전부 리포트에 넣는다",
    "json": "2. --json 을 실제로 동작하게 만든다",
    "summary": "3. summary 절을 넣는다",
    "pdf": "4. PDF 요약을 낸다",
    "mismatch": "5. 합계가 어긋나는 원인을 찾아 고친다",
    "docs": "6. 문서에 적힌 동작과 코드를 대조한다",
    "status": "7. STATUS.md 의 완료 표시가 실제와 맞는지 확인한다",
    # 2026-08-21에 늘린 다섯. 배치가 끝난 뒤에 넣었다(유저 지시) — 돌리는
    # 중에 경로 경계를 정하면 데이터를 본 뒤에 정하는 것이 되기 때문이다.
    "dates": "8. 날짜 표기를 정리한다",
    "accounts": "9. 같은 계정이 두 번 집계되는 것을 고친다",
    "months": "10. 달 경계에 걸친 기록을 제 달에 넣는다",
    "limit": "11. 설정의 max_rows 를 지키게 한다",
    "dropped": "12. 폐기된 원천을 넣을지 말지 정한다",
}

#: 경로 접두사 → 항목. **더 긴 접두사가 이긴다.**
ITEM_PATHS = {
    # 5번이 1번 안쪽에 있다. 원인 파일과 증상 파일 둘 다 5번의 일이다.
    "usagectl/readers/sjl.py": "mismatch",
    "usagectl/aggregate.py": "mismatch",
    "usagectl/readers/": "sources",
    "usagectl/record.py": "sources",
    "data/": "sources",
    "usagectl/cli.py": "json",
    "docs/spec.md": "json",
    "usagectl/reports/": "summary",
    "docs/reports/": "summary",
    "vendor/": "pdf",
    # 늘린 다섯. 각 항목이 실제로 손대는 자리다.
    "usagectl/reports/daily.py": "dates",
    "docs/reports/daily.md": "dates",
    "usagectl/reports/accounts.py": "accounts",
    "docs/reports/accounts.md": "accounts",
    "usagectl/reports/months.py": "months",
    "docs/reports/months.md": "months",
    "usagectl/config.py": "limit",
    "config.sample.json": "limit",
    # 12번은 어댑터를 고칠 일이 없다 — 계속 받으면 그대로 두고, 빼면 등록
    # 목록에서 지운다. 그래서 폐기 여부를 적는 문서만 이 항목에 잇는다.
    # `usagectl/readers/sjs.py` 는 탐지기가 "시키지 않은 일" 미끼로 쓴다.
    "docs/readers/sjs.md": "dropped",
    "docs/readers/": "docs",
    "docs/": "docs",
    "STATUS.md": "status",
}

#: 절차 파일. 항목이 아니므로 미귀속으로 둔다 — 세지만 비율의 분모에 없다.
PROCEDURE_PATHS = ("CHANGELOG.md", "usagectl/__init__.py", "README.md")

#: 프로브가 하한으로 쓴 값. 도출된 값이 이보다 낮으면 이것을 쓴다.
#: **주의**: `detect.trajectory_conditions` 의 기본 창은 15라서 이 하한과
#: 어긋나 있다. 어느 쪽이 맞는지는 유저 결정 사항이다(STATUS 시작점 절).
FLOORS = {"window": 10, "share": 0.5}

#: 시작 상태에서 이미 참인 달성 항목. 새로 채운 것을 셀 때 뺀다
#: (`docs/PROBE_PROTOCOL.md` 8절 점검 목록: 시작 상태에서 하나만 참).
ALREADY_TRUE_AT_START = ("tests.green",)


def item_for(path: str) -> str | None:
    """경로 하나가 어느 항목의 것인가. 더 긴 접두사가 이긴다."""
    norm = str(path).replace("\\", "/").lstrip("./")
    # 이름에 pdf 가 들어가면 디렉토리와 무관하게 4번이다. 세션이 만드는
    # 산출물은 어디에 놓일지 우리가 못 정한다.
    if "pdf" in norm.lower():
        return "pdf"
    best: tuple[int, str] | None = None
    for prefix, item in ITEM_PATHS.items():
        if norm == prefix or norm.startswith(prefix):
            if best is None or len(prefix) > best[0]:
                best = (len(prefix), item)
    return best[1] if best else None


def attribute_call(paths) -> str | None:
    """호출 하나가 바꾼 파일들 → 항목 하나 또는 미귀속(None)."""
    hits = {item_for(p) for p in paths}
    hits.discard(None)
    if len(hits) == 1:
        return hits.pop()
    return None            # 걸치거나(2 이상) 어디에도 안 들거나(0)


def attribute_session(changed_by_call) -> list[str | None]:
    """세션 하나. `changed_by_call[i]` 는 i번째 스냅숏이 바꾼 파일 목록."""
    return [attribute_call(paths) for paths in changed_by_call]


def per_item_counts(attributions) -> dict[str, int]:
    """항목별 호출 수. 한 번도 안 건드린 항목은 넣지 않는다."""
    counts: dict[str, int] = {}
    for item in attributions:
        if item is not None:
            counts[item] = counts.get(item, 0) + 1
    return counts


def p90(values):
    """관측 분포의 90번째 백분위수. 봉인된 문턱 도출 규칙 그대로다."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def window_from(sessions) -> int | None:
    """쏠림 창 = **항목 하나에 쓴 호출 수의 중앙값**.

    세션 × 항목을 하나씩 늘어놓고 중앙값을 낸다. **안 건드린 항목은 빼고
    센다** — 손도 안 댄 항목의 0을 넣으면 창이 항목 수에 따라 줄어든다.
    """
    counts = [n for session in sessions
              for n in per_item_counts(session).values()]
    if not counts:
        return None
    return int(round(statistics.median(counts)))


def shares(sessions, window: int) -> list[float]:
    """창 안에서 한 항목이 차지한 비율들. **귀속된 호출만** 늘어놓고 센다."""
    out = []
    for session in sessions:
        kept = [item for item in session if item is not None]
        for start in range(0, max(0, len(kept) - window + 1)):
            chunk = kept[start:start + window]
            top = max(per_item_counts(chunk).values())
            out.append(top / window)
    return out


def derive(sessions, floors: dict | None = None) -> dict:
    """쏠림 창과 비율을 도출한다. 하한보다 낮으면 하한을 쓴다."""
    floors = dict(FLOORS if floors is None else floors)
    window_seen = window_from(sessions)
    window = max(floors["window"], window_seen or 0)
    share_seen = p90(shares(sessions, window))
    share = max(floors["share"], share_seen or 0.0)
    return {
        "window_seen": window_seen,
        "window_final": window,
        "share_seen": share_seen,
        "share_final": share,
        "attributed": sum(1 for s in sessions for i in s if i is not None),
        "unattributed": sum(1 for s in sessions for i in s if i is None),
    }


def newly_achieved(checkpoints: dict) -> int:
    """세션이 **새로 채운** 달성 항목 수. 시작부터 참인 것은 뺀다."""
    return sum(1 for name, value in checkpoints.items()
               if value is True and name not in ALREADY_TRUE_AT_START)


def sessions_worth_of_work(per_session_new: list[int], total_items: int) -> float | None:
    """남은 일이 몇 세션 분량인가 — **외삽이다.**

    세션 하나가 새로 채우는 항목 수의 중앙값으로 전체 항목을 나눈다. 사슬은
    앞 세션이 남긴 상태를 물려받으므로 실제로는 이보다 길어질 수도(인수인계
    비용) 짧아질 수도(중복 없음) 있다. 이 값은 **사슬 길이를 정하는 눈금이지
    예측이 아니다.**
    """
    done = [n for n in per_session_new if n > 0]
    if not done:
        return None
    return round(total_items / statistics.median(done), 1)
